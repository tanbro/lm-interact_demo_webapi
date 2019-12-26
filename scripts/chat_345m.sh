#!/usr/bin/env bash

/home/liuxy/miniconda3/envs/transfer-learning-conv-ai/bin/python -m interact_demo_webapi \
    --allow-origins "*" \
    --chat-prog /home/kangzh/miniconda3/envs/python3.6/bin/python \
    --chat-pwd /home/kangzh/transfer-learning-conv-ai \
    --chat-args "interact2.py --min_length 16 --max_length 256 --model_checkpoint model_checkpoint_345_32k_v7 --dataset_cache xinli001_jiandanxinli-qa.topics-convai-GPT2BPETokenizer_CN_32K_BPE-cache_v12.1/cache"
