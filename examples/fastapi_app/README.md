# FastAPI example

This application keeps one provider for the application lifetime and creates a
new pydico scope for each HTTP request. The scoped `RequestUnitOfWork` is closed
after FastAPI has completed the request dependency.

Install the optional framework packages and start the application from the
repository root:

```shell
python -m pip install fastapi uvicorn
uvicorn examples.fastapi_app.app:app --reload
```

Try it with:

```shell
curl -X POST http://127.0.0.1:8000/reports -H "Content-Type: application/json" -d "{\"title\":\"Weekly\"}"
curl http://127.0.0.1:8000/reports
```
