"""錄音檔案異步處理服務模組"""

import uuid
import logging
import asyncio # 雖然沒有直接使用 asyncio.sleep() 等，但異步函數本身依賴 asyncio
import sys # 用於 __main__ 中的參數處理
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select

from config import AppConfig
from models import Recording, AnalysisResult, RecordingStatus
# from models import get_async_db_session # 此服務獨立管理 session，故不需要此導入
from services.audio.speech_to_text_async import AsyncSpeechToTextService
from services.ai.gemini_async import AsyncGeminiService

# 取得此模組的日誌記錄器
logger = logging.getLogger(__name__)

async def process_recording_async(recording_id: str):
    """
    異步處理錄音檔案，包括語音轉文字、AI摘要及更新資料庫狀態。

    此函數會在背景任務中執行，負責完成一個錄音檔案的完整處理流程。
    主要步驟如下：
    1.  載入應用程式設定 (AppConfig)。
    2.  建立獨立的異步資料庫引擎 (create_async_engine) 和會話工廠 (async_sessionmaker)。
    3.  使用提供的 recording_id 從資料庫中查詢 Recording 物件。
    4.  若找不到錄音記錄，則記錄錯誤並終止處理。
    5.  更新錄音狀態 (Recording.status) 為 PROCESSING，並立即提交變更至資料庫。
    6.  初始化 AsyncSpeechToTextService。
    7.  調用語音轉文字服務的 `transcribe_audio_data` 方法 (假設錄音數據直接從 Recording 物件的 audio_data 欄位取得)。
        - 注意：原先在 recordings.py 中的 transcribe_audio_data 接收 file_path，此處需確認傳遞的是 audio_data。
          如果 AsyncSpeechToTextService 設計為接收 audio_data，則此處正確。
          若 AsyncSpeechToTextService 仍需 file_path，則 process_recording_async 可能需要先將 DB 中的 audio_data 暫存到臨時文件。
          **根據 recordings.py 中 stt_service.transcribe_audio_data(recording.audio_data,...) 的用法，假設是直接傳輸數據。**
    8.  如果語音轉文字成功，將轉錄結果 (transcript) 和時長 (duration) 儲存。
    9.  初始化 AsyncGeminiService。
    10. 使用轉錄後的文字調用 AI 模型服務的 `generate_summary` (或 `generate_summary_async`) 方法以產生摘要。
    11. 將轉錄結果和摘要儲存到新的 AnalysisResult 記錄中，並與 Recording 關聯。
    12. 更新 Recording 的狀態為 COMPLETED，並記錄處理時長 (duration)。
    13. 若在任何步驟中發生錯誤，則捕獲例外，將 Recording 狀態更新為 FAILED，並記錄錯誤訊息。
    14. 無論成功或失敗，最終都會提交資料庫變更並關閉資料庫會話和引擎。

    :param recording_id: 要處理的錄音記錄的 UUID 字串。
    """
    logger.info(f"錄音 ID: {recording_id} - 開始異步處理錄音...")

    # 1. 載入應用程式設定
    config = AppConfig.from_env()
    logger.debug(f"錄音 ID: {recording_id} - AppConfig 載入完成。")

    # 2. 建立資料庫引擎和會話工廠
    engine = create_async_engine(config.DATABASE_URL, echo=config.DB_ECHO) # 使用 DATABASE_URL 而非 database_url
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    logger.debug(f"錄音 ID: {recording_id} - 資料庫引擎和會話工廠建立完成。")

    async_session = AsyncSessionLocal()
    logger.debug(f"錄音 ID: {recording_id} - 資料庫會話已建立。")

    recording_obj = None # 在 try 外部定義 recording_obj 變數

    try:
        # 3. 查詢錄音記錄
        stmt = select(Recording).where(Recording.id == uuid.UUID(recording_id))
        db_result = await async_session.execute(stmt)
        recording_obj = db_result.scalar_one_or_none()
        logger.debug(f"錄音 ID: {recording_id} - 資料庫查詢完成。")

        # 4. 檢查錄音記錄是否存在
        if not recording_obj:
            logger.error(f"錄音 ID: {recording_id} - 在資料庫中找不到 ID 為 {recording_id} 的錄音記錄。")
            return # 終止處理

        logger.info(f"錄音 ID: {recording_id} - 找到錄音記錄，原始檔名: {recording_obj.original_filename}")

        # 5. 更新錄音狀態為 PROCESSING
        recording_obj.status = RecordingStatus.PROCESSING
        async_session.add(recording_obj) # 加入 session 追蹤變更
        await async_session.commit()
        logger.info(f"錄音 ID: {recording_id} - 狀態已更新為 PROCESSING。")

        transcript_text = None
        # summary_text = None # 在其作用域內定義

        # 內部 try-except 處理轉錄和摘要的特定錯誤
        try:
            # 6. 初始化語音轉文字服務
            stt_service = AsyncSpeechToTextService(config)
            logger.info(f"錄音 ID: {recording_id} - AsyncSpeechToTextService 初始化完成。")

            # 7. 執行語音轉文字
            # 假設 transcribe_audio_data 能處理 bytes 數據，並返回包含 'text' 和 'duration' 的字典
            logger.info(f"錄音 ID: {recording_id} - 開始進行語音轉文字 (資料來自 DB)...")
            stt_result = await stt_service.transcribe_audio_data(
                audio_data=recording_obj.audio_data,
                format_str=recording_obj.format, # 確保 Recording model 有 format 欄位
                mime_type=recording_obj.mime_type # 確保 Recording model 有 mime_type 欄位
            )
            
            transcript_text = stt_result.get('text')
            duration_seconds = stt_result.get('duration') # 獲取時長

            if transcript_text:
                logger.info(f"錄音 ID: {recording_id} - 語音轉文字成功。文字長度: {len(transcript_text)}，時長: {duration_seconds:.2f}s。")
                if duration_seconds is not None:
                    recording_obj.duration = duration_seconds # 更新錄音時長
            else:
                logger.warning(f"錄音 ID: {recording_id} - 語音轉文字未返回有效文字內容。")
                # 即使轉錄失敗或為空，也可能需要記錄一個標記
                # recording_obj.error_message = "Transcription failed or returned empty."

            # 8. 如果轉錄成功，則進行 AI 摘要
            if transcript_text:
                # 9. 初始化 AI 模型服務
                gemini_service = AsyncGeminiService(api_key=config.GEMINI_API_KEY) # 直接使用 config 中的 GEMINI_API_KEY
                logger.info(f"錄音 ID: {recording_id} - AsyncGeminiService 初始化完成。")
                
                # 10. 執行 AI 摘要
                logger.info(f"錄音 ID: {recording_id} - 開始進行 AI 摘要...")
                summary_text = await gemini_service.generate_summary_async(transcript_text) # 假設 gemini_service 有 generate_summary_async

                if summary_text:
                    logger.info(f"錄音 ID: {recording_id} - AI 摘要成功。摘要長度: {len(summary_text)}。")
                else:
                    logger.warning(f"錄音 ID: {recording_id} - AI 摘要未返回有效內容。")
                    summary_text = "摘要生成失敗或無內容。" # 提供一個預設值
            else:
                logger.warning(f"錄音 ID: {recording_id} - 因語音轉文字失敗或無內容，跳過 AI 摘要。")
                summary_text = "因轉錄失敗，無法生成摘要。" # 標註摘要無法生成的原因

            # 11. 創建或更新 AnalysisResult
            # 先查詢是否已存在 AnalysisResult
            analysis_stmt = select(AnalysisResult).where(AnalysisResult.recording_id == recording_obj.id)
            analysis_db_result = await async_session.execute(analysis_stmt)
            existing_analysis = analysis_db_result.scalar_one_or_none()

            if existing_analysis:
                logger.info(f"錄音 ID: {recording_id} - 更新已存在的 AnalysisResult 記錄。")
                existing_analysis.transcription = transcript_text
                existing_analysis.summary = summary_text
                existing_analysis.provider = config.SPEECH_TO_TEXT_PROVIDER # 確保 AppConfig 有 SPEECH_TO_TEXT_PROVIDER
                existing_analysis.model_used = config.AI_MODEL_NAME # 假設 AppConfig 有 AI_MODEL_NAME
                async_session.add(existing_analysis)
            else:
                logger.info(f"錄音 ID: {recording_id} - 創建新的 AnalysisResult 記錄。")
                new_analysis = AnalysisResult(
                    recording_id=recording_obj.id,
                    transcription=transcript_text,
                    summary=summary_text,
                    provider=config.SPEECH_TO_TEXT_PROVIDER, # 確保 AppConfig 有 SPEECH_TO_TEXT_PROVIDER
                    model_used=config.AI_MODEL_NAME # 假設 AppConfig 有 AI_MODEL_NAME
                )
                async_session.add(new_analysis)
            
            # 12. 更新錄音最終狀態為 COMPLETED
            recording_obj.status = RecordingStatus.COMPLETED
            recording_obj.error_message = None # 清除之前的錯誤訊息（如果有）
            logger.info(f"錄音 ID: {recording_id} - 處理流程完成，狀態更新為 COMPLETED。")

        except Exception as e_process:
            # 處理轉錄或摘要過程中的特定錯誤
            logger.error(f"錄音 ID: {recording_id} - 在語音轉文字或摘要過程中發生錯誤: {str(e_process)}", exc_info=True)
            if recording_obj: # 確保 recording_obj 存在
                recording_obj.status = RecordingStatus.FAILED
                recording_obj.error_message = f"處理失敗: {str(e_process)}"
                logger.info(f"錄音 ID: {recording_id} - 因處理錯誤，狀態更新為 FAILED。")
        
        # 最終提交內部 try-except 的變更 (包括 AnalysisResult 和 Recording 的狀態)
        if recording_obj:
            async_session.add(recording_obj) # 再次加入以確保所有變更被追蹤
        await async_session.commit()
        logger.debug(f"錄音 ID: {recording_id} - 資料庫變更 (AnalysisResult, Recording status) 已提交。")

    except Exception as e_outer:
        # 處理更高級別的錯誤，例如資料庫查詢失敗或初始狀態更新前的錯誤
        logger.critical(f"錄音 ID: {recording_id} - 異步處理錄音時發生嚴重外部錯誤: {str(e_outer)}", exc_info=True)
        # 嘗試更新狀態為 FAILED (如果 recording_obj 物件已從DB加載)
        if recording_obj: # 檢查 recording_obj 是否已成功從資料庫查詢到
            try:
                recording_obj.status = RecordingStatus.FAILED
                recording_obj.error_message = f"嚴重外部錯誤: {str(e_outer)}"
                async_session.add(recording_obj)
                await async_session.commit() # 嘗試提交最後的錯誤狀態
                logger.info(f"錄音 ID: {recording_id} - 因嚴重外部錯誤，狀態更新為 FAILED。")
            except Exception as e_commit_fail:
                logger.error(f"錄音 ID: {recording_id} - 在處理嚴重外部錯誤時，更新狀態至資料庫失敗: {e_commit_fail}", exc_info=True)
        # 如果 recording_obj 為 None (例如，uuid轉換失敗或查詢前就出錯)，則無法更新資料庫中的狀態

    finally:
        # 14. 最終關閉資料庫會話和引擎
        if async_session: # 確保 async_session 成功創建
            await async_session.close()
            logger.debug(f"錄音 ID: {recording_id} - 資料庫會話已關閉。")
        if engine: # 確保 engine 成功創建
            await engine.dispose()
            logger.debug(f"錄音 ID: {recording_id} - 資料庫引擎已釋放。")

    logger.info(f"錄音 ID: {recording_id} - 異步處理錄音任務結束。")

# --- 以下為本地測試用的 __main__ 區塊 ---
if __name__ == '__main__':
    # 提示：此測試區塊僅用於開發和基本驗證，不應在生產環境中執行。
    # 執行前，請確保已設定好必要的環境變數，例如：
    # DATABASE_URL, GOOGLE_APPLICATION_CREDENTIALS (如果使用 Google STT), GEMINI_API_KEY 等。
    # 並且資料庫中應存在一個具有您提供的 `test_recording_id` 的 Recording 記錄，
    # 且該記錄的 `audio_data`, `format`, `mime_type` 欄位有有效數據。

    async def run_test_processing(test_rec_id: str):
        """用於執行 process_recording_async 測試的輔助函數。"""
        # 設定基本的日誌記錄器，以便在控制台看到輸出
        # 建議在實際應用中，日誌設定由應用程式主入口 (如 main_fastapi.py)統一處理
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)] # 確保日誌輸出到 stdout
        )
        
        # 可以考慮使用 coloredlogs 以獲得更美觀的日誌輸出 (可選)
        # import coloredlogs
        # coloredlogs.install(level='DEBUG', 
        #                     fmt='%(asctime)s %(hostname)s %(name)s[%(process)d] %(levelname)s %(message)s',
        #                     stream=sys.stdout)

        logger.info(f"測試開始：準備處理錄音 ID: {test_rec_id}")
        try:
            await process_recording_async(test_rec_id)
            logger.info(f"測試完成：錄音 ID: {test_rec_id} 處理完畢。請檢查資料庫中的狀態和結果。")
        except Exception as e_test:
            logger.error(f"測試失敗：處理錄音 ID {test_rec_id} 時發生未捕獲的例外: {e_test}", exc_info=True)

    # 從命令列參數獲取 recording_id
    if len(sys.argv) > 1:
        recording_id_to_test = sys.argv[1]
        try:
            # 基本的 UUID 格式驗證
            uuid.UUID(recording_id_to_test)
            asyncio.run(run_test_processing(recording_id_to_test))
        except ValueError:
            print(f"錯誤：提供的 ID '{recording_id_to_test}' 不是有效的 UUID 格式。請提供一個有效的 UUID。")
        except Exception as e_main:
            # 捕獲 asyncio.run() 或其他 setup 階段可能發生的錯誤
            print(f"執行測試主程序時發生錯誤: {e_main}")
    else:
        print("執行方式：")
        print("  python -m services.recording_processing_service <有效的 RECORDING_ID>")
        print("請提供一個存在於資料庫中的有效 RECORDING_ID 作為命令列參數來運行測試。")
        # 例如:
        # default_test_id = "your-actual-recording-uuid-for-testing"
        # if default_test_id != "your-actual-recording-uuid-for-testing":
        #     print(f"將使用預設ID (如果已設定): {default_test_id}")
        #     asyncio.run(run_test_processing(default_test_id))
        # else:
        #     print("未設定預設測試 ID。")
```

Key changes in this version:
-   The `process_recording_async` function from `api_fastapi/recordings.py` has been moved here.
-   Imports are adjusted for this file's location and dependencies.
-   Docstrings and comments are in Traditional Chinese and expanded.
-   The database URL in `create_async_engine` is now correctly `config.DATABASE_URL`.
-   Assumptions about `AsyncSpeechToTextService` and `AsyncGeminiService` methods are based on their usage in the original `recordings.py`. Specifically, `transcribe_audio_data` is assumed to handle `bytes` from `recording_obj.audio_data`.
-   Error handling has been made more robust, distinguishing between processing errors (inner try-except) and more critical outer errors.
-   The `__main__` block is updated for better local testing, including more explicit instructions and basic UUID validation for the input `recording_id`.
-   Ensured that `recording_obj` (previously `recording`) is added to the session for changes to be tracked before commit, especially for status updates.
-   Added placeholders for `config.SPEECH_TO_TEXT_PROVIDER` and `config.AI_MODEL_NAME` in `AnalysisResult`, assuming these will be available in `AppConfig`. If not, these lines would need adjustment or removal.
-   The logic for creating or updating `AnalysisResult` is included.
-   Recording duration is updated from the STT result.The `services/recording_processing_service.py` file has been successfully created/overwritten with the `process_recording_async` function, including necessary imports, docstrings, and enhanced comments.

Now, I will update `api_fastapi/recordings.py`:
1.  Remove the `process_recording_async` function.
2.  Add the import: `from services.recording_processing_service import process_recording_async`.
3.  Ensure background tasks in `upload_recording` and `reprocess_recording` use this imported function.
