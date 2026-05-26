uv run tensorboard --logdir outputs --host 0.0.0.0 --port 6006

nohup $(which python) -m jupyterlab  --ip=0.0.0.0  --port=8080  --allow-root  --no-browser   --ServerApp.token=''  --ServerApp.password=''   --ServerApp.allow_remote_access=True > ~/jupyter_debug.log 2>&1 &

ss -lntp "sport = :8080" | grep -oP 'pid=\K\d+' | xargs kill -9 2>/dev/null
