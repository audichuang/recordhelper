#!/usr/bin/env python3
"""
SRT 格式比較測試腳本
比較 AssemblyAI 和 Deepgram 產生的 SRT 字幕格式
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
import difflib

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.audio.base import TranscriptionResult
from config import AppConfig


def format_srt_time(seconds: float) -> str:
    """將秒數轉換為 SRT 時間格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_from_segments(segments: list) -> str:
    """從分段資料生成 SRT 格式字幕"""
    srt_lines = []
    
    for i, segment in enumerate(segments, 1):
        start_time = format_srt_time(segment.get('start', 0))
        end_time = format_srt_time(segment.get('end', 0))
        text = segment.get('text', '').strip()
        
        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_time} --> {end_time}")
        srt_lines.append(text)
        srt_lines.append("")  # 空行分隔
    
    return "\n".join(srt_lines)


async def test_assemblyai(file_path: str, config: AppConfig) -> tuple[TranscriptionResult, str]:
    """測試 AssemblyAI 轉錄並生成 SRT"""
    try:
        from services.audio.assemblyai_async import AssemblyAITranscriptionService
        
        service = AssemblyAITranscriptionService(config)
        result = await service.transcribe_audio(file_path)
        
        # AssemblyAI 提供原生 SRT 格式
        srt_content = ""
        if hasattr(result, 'srt_url') and result.srt_url:
            # 如果有 SRT URL，可以下載
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(result.srt_url) as response:
                    if response.status == 200:
                        srt_content = await response.text()
        elif result.segments:
            # 從分段生成 SRT
            srt_content = generate_srt_from_segments(result.segments)
        
        return result, srt_content
    except Exception as e:
        print(f"❌ AssemblyAI 錯誤: {str(e)}")
        return None, ""


async def test_deepgram(file_path: str, config: AppConfig) -> tuple[TranscriptionResult, str]:
    """測試 Deepgram 轉錄並生成 SRT"""
    try:
        from services.audio.deepgram_async import DeepgramTranscriptionService
        
        service = DeepgramTranscriptionService(config)
        result = await service.transcribe_audio(file_path)
        
        # 從 Deepgram 結果生成 SRT
        srt_content = ""
        if result.segments:
            srt_content = generate_srt_from_segments(result.segments)
        
        return result, srt_content
    except Exception as e:
        print(f"❌ Deepgram 錯誤: {str(e)}")
        return None, ""


def compare_srt_files(srt1: str, srt2: str, name1: str = "AssemblyAI", name2: str = "Deepgram"):
    """比較兩個 SRT 檔案的差異"""
    lines1 = srt1.strip().split('\n')
    lines2 = srt2.strip().split('\n')
    
    print(f"\n📊 SRT 格式比較: {name1} vs {name2}")
    print("=" * 60)
    
    # 基本統計
    print(f"\n📈 基本統計:")
    print(f"  {name1}: {len([l for l in lines1 if l and not l.isdigit() and '-->' not in l])} 個字幕段")
    print(f"  {name2}: {len([l for l in lines2 if l and not l.isdigit() and '-->' not in l])} 個字幕段")
    
    # 顯示差異
    diff = difflib.unified_diff(lines1, lines2, fromfile=name1, tofile=name2, lineterm='', n=3)
    diff_lines = list(diff)
    
    if diff_lines:
        print(f"\n🔍 前 20 行差異:")
        for i, line in enumerate(diff_lines[:20]):
            if line.startswith('+'):
                print(f"  + {line[1:]}")
            elif line.startswith('-'):
                print(f"  - {line[1:]}")
            elif line.startswith('@'):
                print(f"\n  {line}")
    else:
        print("\n✅ 兩個 SRT 檔案完全相同!")


async def main():
    """主測試函數"""
    # 檢查命令行參數
    if len(sys.argv) < 2:
        print("使用方式: python test_srt_comparison.py <音檔路徑>")
        print("範例: python test_srt_comparison.py test_audio.mp3")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    if not os.path.exists(audio_file):
        print(f"❌ 找不到音檔: {audio_file}")
        sys.exit(1)
    
    # 載入配置
    config = AppConfig.from_env()
    
    # 檢查 API 金鑰
    has_assemblyai = bool(config.assemblyai_api_keys)
    has_deepgram = bool(config.deepgram_api_keys)
    
    if not has_assemblyai and not has_deepgram:
        print("❌ 請在 .env 檔案中設定 AssemblyAI 或 Deepgram 的 API 金鑰")
        sys.exit(1)
    
    print(f"🎙️ 測試音檔: {audio_file}")
    print(f"📊 檔案大小: {os.path.getsize(audio_file) / 1024 / 1024:.2f} MB")
    print()
    
    results = {}
    srt_files = {}
    
    # 測試 AssemblyAI
    if has_assemblyai:
        print("🥇 測試 AssemblyAI...")
        start_time = datetime.now()
        result, srt_content = await test_assemblyai(audio_file, config)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if result:
            results['AssemblyAI'] = {
                'time': elapsed,
                'text_length': len(result.text),
                'segments': len(result.segments) if result.segments else 0,
                'confidence': result.confidence
            }
            srt_files['AssemblyAI'] = srt_content
            
            # 儲存 SRT 檔案
            with open('assemblyai_output.srt', 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"  ✅ 完成! 耗時: {elapsed:.2f} 秒")
            print(f"  📝 文字長度: {len(result.text)} 字元")
            print(f"  🎯 信心分數: {result.confidence:.2%}" if result.confidence else "")
    
    # 測試 Deepgram
    if has_deepgram:
        print("\n🥈 測試 Deepgram...")
        start_time = datetime.now()
        result, srt_content = await test_deepgram(audio_file, config)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if result:
            results['Deepgram'] = {
                'time': elapsed,
                'text_length': len(result.text),
                'segments': len(result.segments) if result.segments else 0,
                'confidence': result.confidence
            }
            srt_files['Deepgram'] = srt_content
            
            # 儲存 SRT 檔案
            with open('deepgram_output.srt', 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"  ✅ 完成! 耗時: {elapsed:.2f} 秒")
            print(f"  📝 文字長度: {len(result.text)} 字元")
            print(f"  🎯 信心分數: {result.confidence:.2%}" if result.confidence else "")
    
    # 比較結果
    if len(results) >= 2:
        print("\n" + "=" * 60)
        print("📊 整體比較:")
        print("=" * 60)
        
        # 速度比較
        fastest = min(results.items(), key=lambda x: x[1]['time'])
        print(f"\n⚡ 速度冠軍: {fastest[0]} ({fastest[1]['time']:.2f} 秒)")
        
        # SRT 格式比較
        if 'AssemblyAI' in srt_files and 'Deepgram' in srt_files:
            compare_srt_files(srt_files['AssemblyAI'], srt_files['Deepgram'])
        
        # 顯示 SRT 範例
        print("\n📄 SRT 格式範例:")
        for name, srt in srt_files.items():
            print(f"\n--- {name} SRT (前 500 字元) ---")
            print(srt[:500])
            if len(srt) > 500:
                print("...")
    
    # 儲存詳細報告
    report = {
        'test_time': datetime.now().isoformat(),
        'audio_file': audio_file,
        'file_size_mb': os.path.getsize(audio_file) / 1024 / 1024,
        'results': results
    }
    
    with open('srt_comparison_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 詳細報告已儲存至: srt_comparison_report.json")
    print(f"📄 SRT 檔案已儲存:")
    if 'AssemblyAI' in srt_files:
        print(f"  - assemblyai_output.srt")
    if 'Deepgram' in srt_files:
        print(f"  - deepgram_output.srt")


if __name__ == "__main__":
    asyncio.run(main())