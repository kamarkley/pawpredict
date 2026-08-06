from fastapi import FastAPI

app = FastAPI(
    title="PawPredict API",
    description="API for tracking and predicting canine behavior.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the PawPredict API"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


