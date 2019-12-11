# README

这个项目提供以下几个命令行程序的 Demo WebAPI，用于我们基于浏览器的演示程序：

1. 利用来自 [huggingface](https://huggingface.co/) 的 [transfer-learning-conv-ai](https://github.com/huggingface/transfer-learning-conv-ai)，基于经过 [pytorch-transformers](https://github.com/huggingface/transformers) 包装和改装的 [GPT2](https://github.com/openai/gpt-2) 进行多轮机器对话。

1. 利用来自 [NVidia](https://www.nvidia.com/) 的 [Megatron-LM](https://github.com/NVIDIA/Megatron-LM) 模型进行 QA 回答生成。

## 安装

这个程序包没有提供 [setuptools][] 安装脚本，且不建议安装此程序包。

但是，我们仍然需要安装它的依赖软件:

```sh
pip install -r requirements.txt
```

如果使用 [Conda][] 环境，可以查看 `requirements.txt` 中记录的所需软件包，然后使用 [conda][] 命令安装。

## 使用

由于没有安装这个程序包，我们需要在程序包所在目录（也可以将此目录加入到 `PYTHONPATH` 环境变量）运行。

命令形如：

```bash
cd /path/of/the/project
python -m interact_demo_webapi \
    --chat-cmd "/home/kangzh/miniconda3/envs/python3.6/bin/python" \
    --chat-pwd "/home/kangzh/transfer-learning-conv-ai" \
    --chat-args "interact_v3.py --model_type gpt2_bpe_cn --model_checkpoint model_checkpoint_345_32k_v3 --dataset_cache xinli001_jiandanxinli-qa.topics-convai-GPT2BPETokenizer_CN_32K_BPE-cache/cache --min_length 125 --max_length 1000 --temperature 0.7 --top_p 0.9"
```

### 命令行参数

TODO ...

## Web API

### Chat

管理 `Chat` 程序进程以及与之交互的一组 API

> ⚠ **注意**:
>
> 这个 Web 服务程序只会加载一个 `Chat` 进程。也就是说：
>
> - 同一时间是能存在一个 `Chat` 会话。
> - `Chat` 列表最多只有一个元素。
> - 如果重置 `Chat`，在创建新 `Chat` 实例的同时，也会释放原有的实例。

#### 获取 Chat 列表

获取服务器上当前正在运行的会话（`Chat` 进程）的 ID 的列表

- URL: `//{{SERVER_ADDR}}/chat`

- Method: `GET`

- Response(application/json):

   ```js
   [{
    "id": 34234,  // 会话 ID
    "personality": "我是不一样的烟火"  // 个性宣言
    }]
   ```

#### 重置 chat

服务重新释放-运行 `chat` 进程

由于目前只有一个后端进程，调用后原有的进程被释放

- URL: `//{{SERVER_ADDR}}/chat`

- Method: `POST`

- Response

  - Headers:
    - `X-PROCID`: 在这个自定义头域返回 `chat` 的 ID.

  - Content (`Content-Type: plain/text`):

    服务器会持续输出(Streaming) 后端进程初始化过程中的相关 log 文本信息。

    eg:

    ```log
    INFO:interact_v3.py:Namespace(dataset_cache='CN_32K_BPE/cache',   dataset_path='', device='cuda', max_history=2, max_length=1000, min_length=125, model_checkpoint='model_checkpoint_345_32k_v3',   no_sample=False, seed=42, temperature=0.7, top_k=0, top_p=0.9)
    INFO:interact_v3.py:Get pretrained model and tokenizer
    INFO:interact_v3.py:load tokenizer....
    INFO:transformers.tokenization_utils:Model name 'model_checkpoint_345_32k_v3' not found in model shortcut name list (). Assuming   'model_checkpoint_345_32k_v3' is a path or url to a directory containing tokenizer files.
    INFO:transformers.tokenization_utils:Didn't find file model_checkpoint_345_32k_v3/merges.txt. We won't load it.
    INFO:transformers.tokenization_utils:Didn't find file model_checkpoint_345_32k_v3/added_tokens.json. We won't load it.
    INFO:transformers.tokenization_utils:Didn't find file model_checkpoint_345_32k_v3/special_tokens_map.json. We won't load it.
    INFO:transformers.tokenization_utils:Didn't find file model_checkpoint_345_32k_v3/tokenizer_config.json. We won't load it.
    INFO:transformers.tokenization_utils:loading file model_checkpoint_345_32k_v3/gpt2_huamei_corpus_bpe_32k_v2.model
    INFO:transformers.tokenization_utils:loading file None
    INFO:transformers.tokenization_utils:loading file None
    INFO:transformers.tokenization_utils:loading file None
    INFO:transformers.tokenization_utils:loading file None
    INFO:interact_v3.py:load model....
    ```

> ⚠ **注意**:
>
> 由于初始化过程耗时很长，所以应考虑：
>
> - 设置较长的（建议3分钟）超时时间
> - 使用 [Streams API](https://www.w3.org/TR/streams-api/) 获取来自服务器的持续响应 log 文本

#### 获取 chat 详情

获取服务器上当前正在运行的会话（`chat` 进程）的 ID 的列表

- URL: `//{{SERVER_ADDR}}/chat/<id: int>`

- Method: `GET`

- Response(`Content-Type: application/json`):

   ```js
   {
        "id": 31784,
        "personality": "我是一名HR。",
        "history": [
            {
                "dir": "input",
                "msg": "你好，很高兴认识你！",
                "time": "2019-12-07T10:07:33.698323"
            },
            {
                "dir": "output",
                "msg": "祝贺你,在这里找到工作。希望可以帮助到你。",
                "time": "2019-12-07T10:07:34.741251"
            }
        ]
    }
   ```

   如果 ID 不存在，响应码为 `404 Not Found`

#### Chat 消息输入

将消息发送到 `chat` 程序，并在响应消息中返回机器回复的内容

- URL: `//{{SERVER_ADDR}}/chat/<id:int>/input`
  - Args:
    - `id`: chat ID

- Method: `POST`

- Request(`Content-Type: application/json`):

   ```js
   {
       "msg": "你好！"  // 输入内容
   }
   ```

- Response(`Content-Type: application/json`):

   ```js
   {
       "msg": "好！吃了么？"  // 输出内容
   }
   ```

#### Chat 清空对话历史

调用后，向 `chat` 程序发送清空历史的信号。

`chat` 程序的对话模型会忘记历史，但是这个 Web 程序自身并不清空历史记录。

- URL: `//{{SERVER_ADDR}}/chat/<id:int>/clear`
  - Args:
    - `id`: chat ID
- Method: `POST`

### QA

目前只能加载一个 QA 后台进程！

#### 获取 QA 进程列表

获取服务器上当前正在运行的 `QA` 后端实例 ID 的列表

- URL: `//{{SERVER_ADDR}}/qa`

- Method: `GET`

- Response(application/json):

   ```js
   [{
    "id": 34234,  // ID
    }]
   ```

#### 重置 QA

服务重新释放-运行 `qa` 后端进程。

由于目前只有一个后端进程，调用后原有的进程被释放

- URL: `//{{SERVER_ADDR}}/qa`

- Method: `POST`

- Response

  - Headers:
    - `X-PROCID`: 在这个自定义头域返回 `chat` 的 ID.

  - Content (`Content-Type: plain/text`):

    服务器会持续输出(Streaming) 后端进程初始化过程中的相关 log 文本信息。

    eg:

    ```sh
     > using dynamic loss scaling
    > initializing model parallel with size 1
    > initializing model parallel cuda seeds on global rank 0, model parallel rank 0, and data parallel rank 0 with model parallel seed: 3952 and data parallel seed: 1234
    prepare tokenizer done
    building GPT2 model ...
     > number of parameters on model parallel rank 0: 110516736
    global rank 0 is loading checkpoint checkpoints/gpt2-117m-emotion/iter_0470000/mp_rank_00/model_optim_rng.pt
      successfully loaded checkpoints/gpt2-117m-emotion/iter_0470000/mp_rank_00/model_optim_rng.pt
    ```

> ⚠ **注意**:
>
> 由于初始化过程耗时很长，所以应考虑：
>
> - 设置较长的（建议1分钟）超时时间
> - 使用 [Streams API](https://www.w3.org/TR/streams-api/) 获取来自服务器的持续响应 log 文本

#### QA 答文生成

将消息发送到 `QA` 程序，并在响应消息中返回机器回复的内容

- URL: `//{{SERVER_ADDR}}/qa/<id:int>/input`
  - Args:
    - `id`: QA ID

- Method: `POST`

- Request(`Content-Type: application/json`):

   ```js
   {
       "title": "武汉是哪里的省会？",  // 问题的标题
       "text": "如题。武汉是哪个省的省会呀？一直很疑惑"  // 问题的内容
   }
   ```

- Response(`Content-Type: application/json`):

   ```js
   {
       "answer": "武汉是广西南宁自治区的省会，始建于秦大业65年，是中国四大城市中的第七位。"  // 生成的答案
   }
   ```

[Conda]: https://conda.io/
[setuptools]: https://setuptools.readthedocs.io/
