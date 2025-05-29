"""
SRT 字幕格式化工具
提供標準 SRT 格式生成功能
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import timedelta


class SRTFormatter:
    """SRT 字幕格式化器"""
    
    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """
        將秒數轉換為 SRT 時間戳格式 (HH:MM:SS,mmm)
        
        Args:
            seconds: 秒數（支援小數點）
            
        Returns:
            SRT 格式的時間戳，例如 "00:01:23,456"
        """
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        seconds_int = int(td.total_seconds() % 60)
        milliseconds = int((td.total_seconds() * 1000) % 1000)
        
        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"
    
    @staticmethod
    def create_subtitle_entry(index: int, start_time: float, end_time: float, 
                            text: str, speaker: Optional[str] = None) -> str:
        """
        創建單個 SRT 字幕條目
        
        Args:
            index: 字幕序號（從1開始）
            start_time: 開始時間（秒）
            end_time: 結束時間（秒）
            text: 字幕文字
            speaker: 說話者名稱（可選）
            
        Returns:
            格式化的 SRT 條目
        """
        start_ts = SRTFormatter.format_timestamp(start_time)
        end_ts = SRTFormatter.format_timestamp(end_time)
        
        # 如果有說話者，加入標識
        if speaker:
            text = f"[{speaker}] {text}"
        
        return f"{index}\n{start_ts} --> {end_ts}\n{text}\n"
    
    @staticmethod
    def generate_srt_from_words(words: List[Dict[str, Any]], 
                               max_chars_per_line: int = 80,
                               max_duration: float = 5.0) -> str:
        """
        從單詞級時間戳資料生成 SRT 字幕
        
        Args:
            words: 包含單詞時間戳的列表，每個元素應包含:
                   - text: 單詞文字
                   - start: 開始時間（秒）
                   - end: 結束時間（秒）
                   - speaker: 說話者（可選）
            max_chars_per_line: 每行最大字元數
            max_duration: 單個字幕的最大持續時間（秒）
            
        Returns:
            完整的 SRT 格式字幕文字
        """
        if not words:
            return ""
        
        subtitles = []
        current_subtitle = {
            'text': [],
            'start': None,
            'end': None,
            'speaker': None,
            'char_count': 0
        }
        
        for word_data in words:
            word_text = word_data.get('text', '').strip()
            if not word_text:
                continue
                
            word_start = word_data.get('start', 0)
            word_end = word_data.get('end', word_start)
            speaker = word_data.get('speaker')
            
            # 檢查是否需要開始新字幕
            need_new_subtitle = False
            
            # 條件1：當前字幕為空
            if current_subtitle['start'] is None:
                need_new_subtitle = False
            # 條件2：說話者改變
            elif speaker != current_subtitle['speaker']:
                need_new_subtitle = True
            # 條件3：超過最大持續時間
            elif word_start - current_subtitle['start'] > max_duration:
                need_new_subtitle = True
            # 條件4：加上新詞會超過最大字元數
            elif current_subtitle['char_count'] + len(word_text) + 1 > max_chars_per_line:
                need_new_subtitle = True
            # 條件5：遇到句號等結束標點
            elif word_text.endswith(('。', '！', '？', '.', '!', '?')):
                need_new_subtitle = True
            
            if need_new_subtitle and current_subtitle['text']:
                # 保存當前字幕
                subtitles.append({
                    'text': ' '.join(current_subtitle['text']),
                    'start': current_subtitle['start'],
                    'end': current_subtitle['end'],
                    'speaker': current_subtitle['speaker']
                })
                # 重置當前字幕
                current_subtitle = {
                    'text': [],
                    'start': None,
                    'end': None,
                    'speaker': None,
                    'char_count': 0
                }
            
            # 添加單詞到當前字幕
            current_subtitle['text'].append(word_text)
            current_subtitle['char_count'] += len(word_text) + 1
            
            if current_subtitle['start'] is None:
                current_subtitle['start'] = word_start
                current_subtitle['speaker'] = speaker
            
            current_subtitle['end'] = word_end
        
        # 處理最後一個字幕
        if current_subtitle['text']:
            subtitles.append({
                'text': ' '.join(current_subtitle['text']),
                'start': current_subtitle['start'],
                'end': current_subtitle['end'],
                'speaker': current_subtitle['speaker']
            })
        
        # 生成 SRT 格式
        srt_content = []
        for i, subtitle in enumerate(subtitles, 1):
            entry = SRTFormatter.create_subtitle_entry(
                i,
                subtitle['start'],
                subtitle['end'],
                subtitle['text'],
                subtitle['speaker']
            )
            srt_content.append(entry)
        
        return '\n'.join(srt_content)
    
    @staticmethod
    def generate_srt_from_segments(segments: List[Dict[str, Any]]) -> str:
        """
        從分段資料生成 SRT 字幕
        
        Args:
            segments: 包含分段時間戳的列表，每個元素應包含:
                     - text: 分段文字
                     - start: 開始時間（秒）
                     - end: 結束時間（秒）
                     - speaker: 說話者（可選）
                     
        Returns:
            完整的 SRT 格式字幕文字
        """
        if not segments:
            return ""
        
        srt_content = []
        for i, segment in enumerate(segments, 1):
            text = segment.get('text', '').strip()
            if not text:
                continue
                
            start_time = segment.get('start', 0)
            end_time = segment.get('end', start_time)
            speaker = segment.get('speaker')
            
            entry = SRTFormatter.create_subtitle_entry(
                i,
                start_time,
                end_time,
                text,
                speaker
            )
            srt_content.append(entry)
        
        return '\n'.join(srt_content)
    
    @staticmethod
    def parse_srt(srt_content: str) -> List[Dict[str, Any]]:
        """
        解析 SRT 格式內容
        
        Args:
            srt_content: SRT 格式的字幕內容
            
        Returns:
            解析後的字幕列表
        """
        subtitles = []
        
        # 分割成單個字幕條目
        entries = re.split(r'\n\n+', srt_content.strip())
        
        for entry in entries:
            lines = entry.strip().split('\n')
            if len(lines) < 3:
                continue
            
            try:
                # 解析序號
                index = int(lines[0])
                
                # 解析時間戳
                time_match = re.match(
                    r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',
                    lines[1]
                )
                if not time_match:
                    continue
                
                # 計算開始和結束時間（秒）
                start_time = (
                    int(time_match.group(1)) * 3600 +
                    int(time_match.group(2)) * 60 +
                    int(time_match.group(3)) +
                    int(time_match.group(4)) / 1000
                )
                
                end_time = (
                    int(time_match.group(5)) * 3600 +
                    int(time_match.group(6)) * 60 +
                    int(time_match.group(7)) +
                    int(time_match.group(8)) / 1000
                )
                
                # 解析文字（可能多行）
                text = '\n'.join(lines[2:])
                
                # 檢查是否有說話者標識
                speaker = None
                speaker_match = re.match(r'\[([^\]]+)\]\s*(.*)', text)
                if speaker_match:
                    speaker = speaker_match.group(1)
                    text = speaker_match.group(2)
                
                subtitles.append({
                    'index': index,
                    'start': start_time,
                    'end': end_time,
                    'text': text,
                    'speaker': speaker
                })
                
            except (ValueError, IndexError):
                continue
        
        return subtitles