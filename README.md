# README

我们利用来自 [huggingface](https://huggingface.co/) 的 [transfer-learning-conv-ai](https://github.com/huggingface/transfer-learning-conv-ai)，基于经过 [pytorch-transformers](https://github.com/huggingface/transformers) 包装和改装的 [GPT2](https://github.com/openai/gpt-2) 进行多轮机器对话。

这个项目为多轮对话提供基于浏览器的 ChatDemo WebAPI.

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
python -m chardemo \
    --interact-cmd "/home/kangzh/miniconda3/envs/python3.6/bin/python" \
    --interact-pwd "/home/kangzh/transfer-learning-conv-ai" \
    --interact-args "interact_v3.py --model_type gpt2_bpe_cn --model_checkpoint model_checkpoint_345_32k_v3 --dataset_cache xinli001_jiandanxinli-qa.topics-convai-GPT2BPETokenizer_CN_32K_BPE-cache/cache --min_length 125 --max_length 1000 --temperature 0.7 --top_p 0.9"
```

## Web API

### interact

管理 `interact` 程序进程以及与之交互的一组 API

> ⚠ **注意**:
>
> 这个 Web 服务程序只会加载一个 `interact` 进程。也就是说：
>
> - 同一时间是能存在一个 `interact` 会话。
> - `interact` 列表最多只有一个元素。
> - 如果重置 `interact`，在创建新 `interact` 实例的同时，也会释放原有的实例。

#### 获取 interact 列表

获取服务器上当前正在运行的会话（`interact` 进程）的 ID 的列表

- URL: `//{{SERVER_ADDR}}/interact`

- Method: `GET`

- Response(application/json):

   ```js
   [{
    "id": 34234,  // 会话 ID
    "personality": "我是不一样的烟火"  // 个性宣言
    }]
   ```

#### 重置 interact

服务重新释放-运行 `interact` 进程

- URL: `//{{SERVER_ADDR}}/interact`

- Method: `POST`

- Response

  - Headers:
    - `X-INTERACT-ID`: 在这个自定义头域返回 `interact` 的 ID.

  - Content (`Content-Type: plain/text`):

    服务器会持续输出(Streaming) `interact` 初始化过程中的相关 log 文本信息。

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

#### 获取 interact 详情

获取服务器上当前正在运行的会话（`interact` 进程）的 ID 的列表

- URL: `//{{SERVER_ADDR}}/interact/<id: int>`

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

   如果 interact ID 不存在，响应码为 `404 Not Found`

#### `interact` 消息输入

将消息发送到 `interact` 程序，并在响应消息中返回机器回复的内容

- URL: `//{{SERVER_ADDR}}/interact/<id:int>/input`
  - Args:
    - `id`: interact ID

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

#### `interact` 清空对话历史

调用后，向 `interact` 程序发送清空历史的信号。

`interact` 程序的对话模型会忘记历史，但是这个 Web 程序自身并不清空历史记录。

- URL: `//{{SERVER_ADDR}}/interact/<id:int>/clear`
  - Args:
    - `id`: interact ID
- Method: `POST`

[Conda]: https://conda.io/
[setuptools]: https://setuptools.readthedocs.io/
