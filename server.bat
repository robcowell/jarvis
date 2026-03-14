venv/scripts/activate
cls
echo "Starting J.A.R.V.I.S. core"
uvicorn core.server:app --host 0.0.0.0 --port 8000
