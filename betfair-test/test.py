import betfairlightweight
from flumine import Flumine, clients

trading = betfairlightweight.APIClient(
    "xuloodev", "dwm7VFY_xvj1weq1uhu", app_key="SgxnGrgID0NFYfPT", certs="../certs"
)
trading.login()
# client = clients.BetfairClient(trading)

# framework = Flumine(client=client)

event_types = trading.betting.list_event_types()


def format_event_type_result(event):
    return (
        f"EventTypeResult({format_event_type(event.event_type)}, {event.market_count})"
    )


def format_event_type(event_type):
    return f"EventType({event_type.id, event_type.name})"


# Map over the list and print each formatted event
for formatted_event in map(format_event_type_result, event_types):
    print(formatted_event)
