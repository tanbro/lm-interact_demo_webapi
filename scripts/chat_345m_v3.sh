#!/usr/bin/env bash

APP_ALLOW_ORIGINS=www.huameitech.com
APP_CHAT_PROGRAM=/home/kangzh/miniconda3/envs/python3.6/bin/python
APP_CHAT_CWD=/home/kangzh/transfer-learning-conv-ai
APP_CHAT_ARGS="interact2.py --model_checkpoint model_checkpoint_345_32k_v3 --dataset_cache xinli001_jiandanxinli-qa.topics-convai-GPT2BPETokenizer_CN_32K_BPE-cache/cache --min_length 16 --max_length 256"


/home/liuxy/miniconda3/envs/transfer-learning-conv-ai/bin/python -m uvicorn \
    --workers 1 \
    --port 8090 \
    lmdemo:app
