from shortGPT.audio.voice_module import VoiceModule
from shortGPT.config.languages import Language
from shortGPT.engine.content_short_engine import ContentShortEngine
from shortGPT.gpt.gpt_chat_video import generateFactsScript


class FactsShortEngine(ContentShortEngine):

    def __init__(self, voiceModule: VoiceModule, facts_type: str, background_video_name: str, background_music_name: str,short_id="",
                 num_images=None, watermark=None, language:Language = Language.ENGLISH):
        super().__init__(short_id=short_id, short_type="facts_shorts", background_video_name=background_video_name, background_music_name=background_music_name,
                 num_images=num_images, watermark=watermark, language=language, voiceModule=voiceModule)
        
        self._db_facts_type = facts_type

    def _generateScript(self):
        if not self._db_script:
            self.logger("1/11 Generating the script about your topic...")
            facts_prompt = self._db_facts_type if self._db_facts_type else "Interesting facts"
            chat_prompt = facts_prompt
            
            # Use the imported function
            self._db_script = generateFactsScript(chat_prompt + " (must be under 30 seconds)")
        return self._db_script


