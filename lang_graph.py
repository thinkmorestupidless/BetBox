from typing import Annotated

from dotenv import find_dotenv, load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from langchain_community.tools.tavily_search import TavilySearchResults


load_dotenv(find_dotenv())


class State(TypedDict):
    message: Annotated[list, add_messages]


graph_builder = StateGraph(State)

llm = ChatAnthropic(model="claude-3-5-sonnet-20240620")


def chatbot(state: State):
    return {"message": [llm.invoke(state["message"])]}


tool = TavilySearchResults(max_results=3)
tools = [tool]
tool.invoke()


graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()


def stream_graph_updates(user_input: str):
    for event in graph.stream({"message": [("user", user_input)]}):
        for value in event.values():
            print("Assistant:", value["message"][-1].content)


while True:
    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        stream_graph_updates(user_input)
    except:
        user_input = "What do you know about LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break
