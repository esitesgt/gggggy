import os
import MetaTrader5 as mt5


def connect() -> bool:
    terminal_path = os.getenv("MT5_TERMINAL_PATH")
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")

    kwargs = {}
    if login:
        kwargs["login"] = int(login)
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    return mt5.initialize(terminal_path, **kwargs) if terminal_path else mt5.initialize(**kwargs)


def status() -> dict:
    if not connect():
        return {"connected": False, "error": mt5.last_error()}

    account = mt5.account_info()
    terminal = mt5.terminal_info()
    return {
        "connected": True,
        "account": account._asdict() if account else None,
        "terminal": terminal._asdict() if terminal else None,
    }


if __name__ == "__main__":
    print(status())
    mt5.shutdown()
