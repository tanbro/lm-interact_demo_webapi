#!/usr/bin/env bash

/home/liuxy/miniconda3/envs/transfer-learning-conv-ai/bin/python -m uvicorn \
    --workers 1 \
    --log-level debug \
    --env-file .env.production \
    --port 8090 \
    lmdemo:app
