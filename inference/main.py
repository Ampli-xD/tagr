import os


def main() -> None:
    mode = os.getenv("INFERENCE_MODE", "server").lower()

    if mode == "runpod":
        from handler import handler
        import runpod

        runpod.serverless.start({"handler": handler})
        return

    import uvicorn

    host = os.getenv("INFERENCE_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("INFERENCE_PORT", "8001")))
    uvicorn.run("server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
