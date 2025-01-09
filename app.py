import os
from typing import Literal
import betfairlightweight
from betfairlightweight.filters import market_filter

import chainlit as cl
from dotenv import find_dotenv, load_dotenv
from langchain.schema.runnable.config import RunnableConfig
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from langchain.agents import Tool
from langchain_core.tools import StructuredTool

load_dotenv(find_dotenv())

trading = betfairlightweight.APIClient(
    username=os.environ["BETBOX_BETFAIR_USERNAME"],
    password=os.environ["BETBOX_BETFAIR_PASSWORD"],
    app_key=os.environ["BETBOX_BETFAIR_APP_KEY"],
    certs=os.environ["BETBOX_BETFAIR_CERT_PATH"],
)
trading.login()


def format_event_type_result(event):
    return (
        f"EventTypeResult({format_event_type(event.event_type)}, {event.market_count})"
    )


def format_competition_result(competition):
    return f"CompetitionResult(competition = {format_competition(competition.competition)}, market_count = {competition.market_count}, competition_region = {competition.competition_region})"


def format_competition(competition):
    return f"Competition(id = {competition.id}, name = {competition.name})"


def format_event_type(event_type):
    return f"EventType({event_type.id, event_type.name})"


@tool
def get_prices(query: str):
    """Use this to get prices for a sports betting market"""
    return "home team is 1.4, the draw is 2.4 and the away team is 4.8"


def get_event_types():
    print("getting event types")
    event_types = trading.betting.list_event_types()
    for formatted_event in map(format_event_type_result, event_types):
        print(formatted_event)
    return [
        {"id": event_type.event_type.id, "name": event_type.event_type.name}
        for event_type in event_types
    ]


class GetCompetitionsInput(BaseModel):
    event_type_ids: list[str] = Field(
        description="a list of event type ids for which we want to get a list of competitions"
    )


# @tool("get-competitions-betfair", args_schema=GetCompetitionsInput, return_direct=True)
def get_competitions(event_type_ids: list[str]):
    """Use this to get a list of competitions that can have bets placed on them for the given event types"""
    print(f"getting competitions with event type ids {event_type_ids}")
    competitions = trading.betting.list_competitions(
        filter=market_filter(event_type_ids=event_type_ids)
    )
    for formatted_competition in map(format_competition_result, competitions):
        print(formatted_competition)
    return [competition.competition for competition in competitions]


get_all_event_types_tool = StructuredTool.from_function(
    func=get_event_types,
    name="get_event_types",
    description=(
        "Use this to retrieve the list of all event types and their IDs. Event Types are a synonym for a Sport. The output will contain lines in the form 'ID: 100, Name: soccer', etc."
    ),
)

get_competitions_by_event_type_tool = StructuredTool.from_function(
    name="get_competitions",
    func=get_competitions,
    description=(
        "Use this to retrieve all competitions for a list of event type ids. If you need a list of competitions for a specific sport then just pass the event type id that relates to the sport you're looking for"
    ),
)


@tool
def get_events():
    """Returns a list of Events (i.e, Reading vs. Man United) associated with the markets selected by the MarketFilter."""


@tool
def get_weather(city: Literal["nyc", "sf"]):
    """Use this to get weather information."""
    if city == "nyc":
        return "It might be cloudy in nyc"
    elif city == "sf":
        return "It's always sunny in sf"
    else:
        raise AssertionError("Unknown city")


tools = [
    get_weather,
    get_all_event_types_tool,
    get_competitions_by_event_type_tool,
    get_prices,
]
model = ChatOpenAI(model_name="gpt-4o-2024-11-20", temperature=0)
final_model = ChatOpenAI(model_name="gpt-4o-2024-11-20", temperature=0)

model = model.bind_tools(tools)
# NOTE: this is where we're adding a tag that we'll can use later to filter the model stream events to only the model called in the final node.
# This is not necessary if you call a single LLM but might be important in case you call multiple models within the node and want to filter events
# from only one of them.
final_model = final_model.with_config(tags=["final_node"])
tool_node = ToolNode(tools=tools)

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import MessagesState
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage


def should_continue(state: MessagesState) -> Literal["tools", "final"]:
    messages = state["messages"]
    last_message = messages[-1]
    # If the LLM makes a tool call, then we route to the "tools" node
    print(f"tool calls? {last_message.tool_calls}")
    if last_message.tool_calls:
        return "tools"
    # Otherwise, we stop (reply to the user)
    return "final"


def call_model(state: MessagesState):
    messages = state["messages"]
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


def call_final_model(state: MessagesState):
    messages = state["messages"]
    print(f"there are {len(messages)} messages")
    for message in messages:
        print(f"{message}")
    first_message = messages[0]
    last_ai_message = messages[-1]
    response = final_model.invoke(
        [
            SystemMessage(
                "You are a helpful assistant that generates answers for professional sports market traders. Your job is to take the original request '{first_message.content}' and answer the question using the information provided in the last message from the assistant."
            ),
            HumanMessage(last_ai_message.content),
        ]
    )
    # overwrite the last AI message from the agent
    response.id = last_ai_message.id
    return {"messages": [response]}


builder = StateGraph(MessagesState)

builder.add_node("agent", call_model)
builder.add_node("tools", tool_node)
# add a separate final node
builder.add_node("final", call_final_model)

builder.add_edge(START, "agent")
builder.add_conditional_edges(
    "agent",
    should_continue,
)

builder.add_edge("tools", "agent")
builder.add_edge("final", END)

graph = builder.compile()


@cl.on_message
async def on_message(msg: cl.Message):
    config = {"configurable": {"thread_id": cl.context.session.id}}
    cb = cl.LangchainCallbackHandler()
    final_answer = cl.Message(content="")

    for msg, metadata in graph.stream(
        {"messages": [HumanMessage(content=msg.content)]},
        stream_mode="messages",
        config=RunnableConfig(callbacks=[cb], **config),
    ):
        if (
            msg.content
            and not isinstance(msg, HumanMessage)
            and metadata["langgraph_node"] == "final"
        ):
            await final_answer.stream_token(msg.content)

    await final_answer.send()
