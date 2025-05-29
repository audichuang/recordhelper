#!/usr/bin/env python
"""
測試真實世界場景的 SRT 句子級別分割
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.audio.srt_formatter import SRTFormatter

def test_real_world_conversation():
    """測試真實對話場景"""
    
    # 模擬真實對話的單詞級時間戳數據
    words = [
        # 第一句
        {"text": "今天", "start": 0.0, "end": 0.3},
        {"text": "的", "start": 0.3, "end": 0.4},
        {"text": "會議", "start": 0.4, "end": 0.7},
        {"text": "主要", "start": 0.7, "end": 1.0},
        {"text": "討論", "start": 1.0, "end": 1.3},
        {"text": "三個", "start": 1.3, "end": 1.6},
        {"text": "議題", "start": 1.6, "end": 1.9},
        {"text": "。", "start": 1.9, "end": 2.0},
        
        # 第二句
        {"text": "首先", "start": 2.2, "end": 2.5},
        {"text": "，", "start": 2.5, "end": 2.6},
        {"text": "我們", "start": 2.6, "end": 2.8},
        {"text": "要", "start": 2.8, "end": 2.9},
        {"text": "檢討", "start": 2.9, "end": 3.2},
        {"text": "上個月", "start": 3.2, "end": 3.6},
        {"text": "的", "start": 3.6, "end": 3.7},
        {"text": "銷售", "start": 3.7, "end": 4.0},
        {"text": "業績", "start": 4.0, "end": 4.3},
        {"text": "；", "start": 4.3, "end": 4.4},
        
        # 第三句（接續前面）
        {"text": "其次", "start": 4.6, "end": 4.9},
        {"text": "，", "start": 4.9, "end": 5.0},
        {"text": "要", "start": 5.0, "end": 5.1},
        {"text": "制定", "start": 5.1, "end": 5.4},
        {"text": "下", "start": 5.4, "end": 5.5},
        {"text": "季度", "start": 5.5, "end": 5.8},
        {"text": "的", "start": 5.8, "end": 5.9},
        {"text": "目標", "start": 5.9, "end": 6.2},
        {"text": "。", "start": 6.2, "end": 6.3},
        
        # 第四句（問句）
        {"text": "大家", "start": 6.8, "end": 7.1},
        {"text": "對", "start": 7.1, "end": 7.2},
        {"text": "這些", "start": 7.2, "end": 7.4},
        {"text": "安排", "start": 7.4, "end": 7.7},
        {"text": "有", "start": 7.7, "end": 7.8},
        {"text": "什麼", "start": 7.8, "end": 8.0},
        {"text": "意見", "start": 8.0, "end": 8.3},
        {"text": "嗎", "start": 8.3, "end": 8.4},
        {"text": "？", "start": 8.4, "end": 8.5},
    ]
    
    print("=== 測試真實對話場景 ===\n")
    
    # 生成句子級別 SRT
    srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
    print("SRT 輸出:")
    print(srt_content)
    
    # 解析結果
    subtitles = SRTFormatter.parse_srt(srt_content)
    print(f"\n解析結果 - 字幕塊數量: {len(subtitles)}")
    for i, sub in enumerate(subtitles, 1):
        print(f"  字幕 {i} ({sub['start']:.1f}s - {sub['end']:.1f}s): {sub['text']}")

def test_long_sentence():
    """測試長句子的處理"""
    
    # 生成一個很長的句子
    long_sentence_words = []
    start_time = 0.0
    
    # 長句子的詞彙
    text_parts = [
        "根據", "最新", "的", "市場", "調查", "報告", "顯示", "，",
        "我們", "公司", "在", "過去", "一年", "中", "的", "整體",
        "業績", "表現", "相當", "優異", "，", "不僅", "達成", "了",
        "年初", "設定", "的", "所有", "目標", "，", "還", "在",
        "多個", "關鍵", "指標", "上", "超越", "了", "預期", "，",
        "這", "主要", "歸功於", "團隊", "的", "努力", "以及", "正確",
        "的", "策略", "方向", "。"
    ]
    
    for text in text_parts:
        duration = 0.3 if text in ['，', '。'] else 0.4
        long_sentence_words.append({
            "text": text,
            "start": start_time,
            "end": start_time + duration
        })
        start_time += duration
    
    print("\n=== 測試長句子處理 ===\n")
    
    # 生成句子級別 SRT（應該在句號處分割）
    srt_content = SRTFormatter.generate_srt_from_words(long_sentence_words, 
                                                       sentence_level=True,
                                                       max_chars_per_line=100)
    print("SRT 輸出:")
    print(srt_content)
    
    subtitles = SRTFormatter.parse_srt(srt_content)
    print(f"\n解析結果 - 字幕塊數量: {len(subtitles)}")
    for i, sub in enumerate(subtitles, 1):
        print(f"  字幕 {i}: {sub['text'][:50]}..." if len(sub['text']) > 50 else f"  字幕 {i}: {sub['text']}")

def test_speaker_changes():
    """測試說話者變換的處理"""
    
    words = [
        # Speaker A
        {"text": "你好", "start": 0.0, "end": 0.3, "speaker": "A"},
        {"text": "，", "start": 0.3, "end": 0.4, "speaker": "A"},
        {"text": "請問", "start": 0.4, "end": 0.7, "speaker": "A"},
        {"text": "貴", "start": 0.7, "end": 0.9, "speaker": "A"},
        {"text": "姓", "start": 0.9, "end": 1.1, "speaker": "A"},
        {"text": "？", "start": 1.1, "end": 1.2, "speaker": "A"},
        
        # Speaker B
        {"text": "我", "start": 1.5, "end": 1.7, "speaker": "B"},
        {"text": "姓", "start": 1.7, "end": 1.9, "speaker": "B"},
        {"text": "王", "start": 1.9, "end": 2.1, "speaker": "B"},
        {"text": "。", "start": 2.1, "end": 2.2, "speaker": "B"},
        
        # Speaker A again
        {"text": "很", "start": 2.5, "end": 2.7, "speaker": "A"},
        {"text": "高興", "start": 2.7, "end": 3.0, "speaker": "A"},
        {"text": "認識", "start": 3.0, "end": 3.3, "speaker": "A"},
        {"text": "你", "start": 3.3, "end": 3.5, "speaker": "A"},
        {"text": "！", "start": 3.5, "end": 3.6, "speaker": "A"},
    ]
    
    print("\n=== 測試說話者變換處理 ===\n")
    
    srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
    print("SRT 輸出:")
    print(srt_content)
    
    subtitles = SRTFormatter.parse_srt(srt_content)
    print(f"\n解析結果 - 字幕塊數量: {len(subtitles)}")
    for i, sub in enumerate(subtitles, 1):
        print(f"  字幕 {i}: {sub['text']}")
        if sub['speaker']:
            print(f"        說話者: {sub['speaker']}")

if __name__ == "__main__":
    test_real_world_conversation()
    test_long_sentence()
    test_speaker_changes()