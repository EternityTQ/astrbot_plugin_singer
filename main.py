from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

import os
import json
import difflib
from astrbot.api.all import *

@register("astrbot_plugin_singer", "YourName", "动漫歌手点歌插件", "1.0.0")
class SingerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 路径初始化
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.audio_dir = os.path.join(self.plugin_dir, "audio")
        self.alias_file = os.path.join(self.plugin_dir, "aliases.json")
        
        # 确保音频文件夹存在
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # 加载配置并构建扁平化映射表 (别名 -> 真实文件名)
        self.aliases = self._load_aliases()
        self.name_to_file = {}
        self._build_mapping()

    def _load_aliases(self) -> dict:
        """加载 JSON 别名配置"""
        if not os.path.exists(self.alias_file):
            # 如果没有配置文件，生成一个默认的空模板
            with open(self.alias_file, "w", encoding="utf-8") as f:
                json.dump({"example_song": ["示例歌曲", "测试歌曲"]}, f, ensure_ascii=False, indent=2)
            return {}
        with open(self.alias_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_mapping(self):
        """将 JSON 字典拍平，方便进行模糊匹配"""
        for filename, alias_list in self.aliases.items():
            self.name_to_file[filename] = filename  # 真实文件名也作为可触发的词
            for alias in alias_list:
                self.name_to_file[alias] = filename

    def _match_song(self, requested_song: str):
        """
        进行模糊匹配并返回音频路径。
        Returns: (匹配到的名称, 绝对路径) 或者 (None, None)
        """
        all_names = list(self.name_to_file.keys())
        
        # 使用 Python 内置库进行相似度匹配
        # n=1 表示返回最接近的一个结果，cutoff=0.5 是相似度阈值 (0-1之间，越大越严格)
        # 如果用户说 "放一首洗海带"，匹配 "洗海带" 毫无压力
        matches = difflib.get_close_matches(requested_song, all_names, n=1, cutoff=0.5)
        
        if not matches:
            return None, None
            
        best_match_name = matches[0]
        target_filename = self.name_to_file[best_match_name]
        
        # NapCat 原生支持绝对路径的 mp3 文件
        file_path = os.path.abspath(os.path.join(self.audio_dir, f"{target_filename}.mp3"))
        
        if os.path.exists(file_path):
            return best_match_name, file_path
            
        return None, None

    @llm_tool(name="sing_a_song")
    async def sing_a_song(self, event: AstrMessageEvent, song_name: str):
        '''
        当用户要求你唱歌、点歌、或者播放某首歌曲时，必须调用此工具。
        
        Args:
            song_name(string): 用户想要听的歌曲名称。请直接提取用户的话，不要自己编造或翻译。
        '''
        matched_name, audio_path = self._match_song(song_name)
        
        if audio_path:
            # 1. 向用户发送语音
            yield event.chain_result([
                Plain(f"好呀~ 为你献上这首《{matched_name}》！\n"),
                Record(file=audio_path)
            ])
            # 2. 关键修复：给 LLM 返回一个结果，打断它的复读机循环
            return f"执行成功，已经向用户发送了《{matched_name}》的语音。请不要再回复其他内容。"
        else:
            # 1. 没找到歌曲，向用户道歉
            yield event.chain_result([
                Plain(f"唔...你点的《{song_name}》我暂时还没学会呢，或者是我没听清？要不要换一首我拿手的试试看~")
            ])
            # 2. 关键修复：同样告诉 LLM 执行结果
            return f"执行失败，本地没有《{song_name}》这首歌，已告知用户。"