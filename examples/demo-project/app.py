from fastapi import FastAPI

app = FastAPI(title="Demo FastAPI")


def fizzbuzz(number: int) -> str:
    if number % 3 == 0:
        return "Fizz"
    if number % 5 == 0:
        return "Buzz"
    if number % 15 == 0:
        return "FizzBuzz"
    return str(number)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/fizzbuzz/{number}")
def fizzbuzz_endpoint(number: int) -> dict[str, str]:
    return {"value": fizzbuzz(number)}
