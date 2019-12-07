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
    --interact-args "interact.py --model_type gpt2_cn --model_checkpoint ./model_checkpoint_117 --dataset_cache ./dataset_cache_GPT2Tokenizer_cn/cache  --min_length 125 --max_length 1000  --temperature 0.6 --top_p 0.9"
```

## Web API

### interact

管理 `interact` 程序进程以及与之交互的一组 API

> ⚠ **注意**:
>
> 这个 Web 服务程序只会加载一个 `interact` 进程。也就是说，同一时间是能存在一个会话。
> 返回的会话列表最多只有一个元素。

#### 获取会话 ID 的列表

获取服务器上当前正在运行的会话（`interact` 进程）的 ID 的列表

- URL: `//{{SERVER_ADDR}}/interact`

- Method: `GET`

- Response:

   ```js
   {
       "id": 34234,  // 会话 ID
   }
   ```

#### 获取会话信息

获取服务器上当前正在运行的会话（`interact` 进程）的 ID 的列表

- URL: `//{{SERVER_ADDR}}/interact/<id: int>`

- Method: `GET`

- Response:

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

   如果没有会话 ID 不存在，响应码为 `404 Not Found`

#### 重置会话

服务重新释放-运行 `interact` 进程

- URL: `//{{SERVER_ADDR}}/interact/reset`

- Method: `POST`

- Response:

   ```js
   {
       "id": 34234,  // 会话 ID
       "personality": "我是不一样的烟火"  // 个性宣言
   }
   ```

#### 消息输入

将消息发送到 `interact` 程序，并返回机器回复的内容

- URL: `//{{SERVER_ADDR}}/interact/<id:int>/input`
  - Args:
    - `id`: 会话 ID

- Method: `POST`

- Request:

   ```js
   {
       "msg": "你好！"  // 输入内容
   }
   ```

- Response:

   ```js
   {
       "msg": "好！吃了么？"  // 输出内容
   }
   ```

[Conda]: https://conda.io/
[setuptools]: https://setuptools.readthedocs.io/
