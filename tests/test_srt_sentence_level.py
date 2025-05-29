#!/usr/bin/env python
"""
測試 SRT 句子級別分割功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.audio.srt_formatter import SRTFormatter

def test_sentence_level_srt():
    """測試句子級別的 SRT 生成"""
    
    # 模擬單詞級時間戳數據
    words = [
        {"text": "你好", "start": 0.0, "end": 0.5},
        {"text": "，", "start": 0.5, "end": 0.6},
        {"text": "我", "start": 0.7, "end": 0.9},
        {"text": "是", "start": 0.9, "end": 1.1},
        {"text": "AI", "start": 1.1, "end": 1.5},
        {"text": "助手", "start": 1.5, "end": 2.0},
        {"text": "。", "start": 2.0, "end": 2.1},  # 第一句結束
        {"text": "今天", "start": 2.5, "end": 2.9},
        {"text": "天氣", "start": 2.9, "end": 3.3},
        {"text": "真的", "start": 3.3, "end": 3.6},
        {"text": "很", "start": 3.6, "end": 3.8},
        {"text": "好", "start": 3.8, "end": 4.0},
        {"text": "！", "start": 4.0, "end": 4.1},  # 第二句結束
        {"text": "你", "start": 4.5, "end": 4.7},
        {"text": "有", "start": 4.7, "end": 4.9},
        {"text": "什麼", "start": 4.9, "end": 5.2},
        {"text": "需要", "start": 5.2, "end": 5.5},
        {"text": "幫助", "start": 5.5, "end": 5.9},
        {"text": "的", "start": 5.9, "end": 6.0},
        {"text": "嗎", "start": 6.0, "end": 6.2},
        {"text": "？", "start": 6.2, "end": 6.3},  # 第三句結束
    ]
    
    print("=== 測試句子級別 SRT 生成 ===\n")
    
    # 啟用句子級別分割
    srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
    print("句子級別 SRT 輸出:")
    print(srt_content)
    print("\n" + "="*50 + "\n")
    
    # 禁用句子級別分割（傳統方式）
    srt_content_traditional = SRTFormatter.generate_srt_from_words(words, sentence_level=False)
    print("傳統 SRT 輸出（非句子級別）:")
    print(srt_content_traditional)
    
    # 解析並顯示結果
    print("\n=== 解析結果比較 ===\n")
    
    # 解析句子級別結果
    sentence_subtitles = SRTFormatter.parse_srt(srt_content)
    print(f"句子級別字幕塊數量: {len(sentence_subtitles)}")
    for i, sub in enumerate(sentence_subtitles, 1):
        print(f"  字幕 {i}: {sub['text']}")
    
    print()
    
    # 解析傳統結果
    traditional_subtitles = SRTFormatter.parse_srt(srt_content_traditional)
    print(f"傳統字幕塊數量: {len(traditional_subtitles)}")
    for i, sub in enumerate(traditional_subtitles, 1):
        print(f"  字幕 {i}: {sub['text']}")

def test_mixed_punctuation():
    """測試混合標點符號的情況"""
    
    words = [
        {"text": "他", "start": 0.0, "end": 0.2},
        {"text": "說", "start": 0.2, "end": 0.4},
        {"text": "：", "start": 0.4, "end": 0.5},
        {"text": "「", "start": 0.5, "end": 0.6},
        {"text": "今天", "start": 0.6, "end": 1.0},
        {"text": "真", "start": 1.0, "end": 1.2},
        {"text": "開心", "start": 1.2, "end": 1.6},
        {"text": "！", "start": 1.6, "end": 1.7},
        {"text": "」", "start": 1.7, "end": 1.8},  # 引號結束
        {"text": "然後", "start": 2.0, "end": 2.4},
        {"text": "他", "start": 2.4, "end": 2.6},
        {"text": "笑", "start": 2.6, "end": 2.8},
        {"text": "了", "start": 2.8, "end": 3.0},
        {"text": "。", "start": 3.0, "end": 3.1},
    ]
    
    print("\n=== 測試混合標點符號 ===\n")
    
    srt_content = SRTFormatter.generate_srt_from_words(words, sentence_level=True)
    print("SRT 輸出:")
    print(srt_content)
    
    subtitles = SRTFormatter.parse_srt(srt_content)
    print(f"\n解析結果 - 字幕塊數量: {len(subtitles)}")
    for i, sub in enumerate(subtitles, 1):
        print(f"  字幕 {i}: {sub['text']}")

if __name__ == "__main__":
    test_sentence_level_srt()
    test_mixed_punctuation()