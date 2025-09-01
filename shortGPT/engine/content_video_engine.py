import datetime
import os
import re
import shutil

from shortGPT.api_utils.pexels_api import getBestVideo
from shortGPT.audio import audio_utils
from shortGPT.audio.audio_duration import get_asset_duration
from shortGPT.audio.voice_module import VoiceModule
from shortGPT.config.asset_db import AssetDatabase
from shortGPT.config.languages import Language
from shortGPT.editing_framework.editing_engine import (EditingEngine,
                                                       EditingStep)
from shortGPT.editing_utils import captions
from shortGPT.engine.abstract_content_engine import AbstractContentEngine
from shortGPT.gpt import gpt_editing, gpt_translate, gpt_yt


class ContentVideoEngine(AbstractContentEngine):

    def __init__(self, voiceModule: VoiceModule, script: str, background_music_name="", id="",
                 watermark=None, isVerticalFormat=False, language: Language = Language.ENGLISH):
        super().__init__(id, "general_video", language, voiceModule)
        if not id:
            if (watermark):
                self._db_watermark = watermark
            if background_music_name:
                self._db_background_music_name = background_music_name
            self._db_script = script
            self._db_format_vertical = isVerticalFormat

        self.stepDict = {
            1:  self._generateTempAudio,
            2:  self._speedUpAudio,
            3:  self._timeCaptions,
            4:  self._generateImageQueries,  # New step for image queries
            5:  self._generateVideoSearchTerms,
            6:  self._generateVideoUrls,
            7:  self._chooseBackgroundMusic,
            8:  self._prepareBackgroundAssets,
            9: self._prepareCustomAssets,
            10: self._editAndRenderShort,
            11: self._addMetadata
        }

    def _generateTempAudio(self):
        if not self._db_script:
            raise NotImplementedError("generateScript method must set self._db_script.")
        if (self._db_temp_audio_path):
            return
        self.verifyParameters(text=self._db_script)
        
        # Check if script is too long (rough estimate: 3 words per second for 30 seconds = 90 words max)
        word_count = len(self._db_script.split())
        if word_count > 90:
            self.logger("Warning: Script exceeds recommended length for 30-second video. Trimming...")
            words = self._db_script.split()
            self._db_script = ' '.join(words[:90]) + "..."
            
        script = self._db_script
        if (self._db_language != Language.ENGLISH.value):
            self._db_translated_script = gpt_translate.translateContent(script, self._db_language)
            script = self._db_translated_script
        self._db_temp_audio_path = self.voiceModule.generate_voice(
            script, self.dynamicAssetDir + "temp_audio_path.wav")

    def _speedUpAudio(self):
        if (self._db_audio_path):
            return
        self.verifyParameters(tempAudioPath=self._db_temp_audio_path)
        # Since the video is not supposed to be a short( less than 60sec), there is no reason to speed it up
        self._db_audio_path = self._db_temp_audio_path
        return
        self._db_audio_path = audio_utils.speedUpAudio(
            self._db_temp_audio_path, self.dynamicAssetDir+"audio_voice.wav")

    def _timeCaptions(self):
        self.verifyParameters(audioPath=self._db_audio_path)
        whisper_analysis = audio_utils.audioToText(self._db_audio_path)
        max_len = 15
        if not self._db_format_vertical:
            max_len = 30
        self._db_timed_captions = captions.getCaptionsWithTime(
            whisper_analysis, maxCaptionSize=max_len)

    def _generateImageQueries(self):
        """Generate image queries based on the transcript to match key topics in the video."""
        self.verifyParameters(captionsTimed=self._db_timed_captions)
        self.logger("Generating specific image queries based on transcript content...")
        
        # Get total video duration for generating evenly distributed timestamps
        total_duration = self._db_timed_captions[-1][0][1]  # Last caption's end time
        
        # Determine number of images based on video length (1 image every ~5 seconds)
        num_images = min(int(total_duration / 5), 10)  # Cap at 10 images
        num_images = max(num_images, 5)  # At least 5 images
        
        # Identify main topic from transcript for better queries
        all_text = " ".join([text for _, text in self._db_timed_captions])
        if "hyundai" in all_text.lower() or "genesis" in all_text.lower():
            self._db_main_topic = "Hyundai Genesis"
        else:
            # Try to extract main topic from text
            self._db_main_topic = None
        
        self.logger(f"[DEBUG] Main topic for this short: {self._db_main_topic}")
        
        # Generate image queries using LLM
        image_pairs = gpt_editing.getImageQueryPairs(self._db_timed_captions, n=num_images)
        
        # Convert to the format expected by the renderer
        self._db_image_queries = []
        for (t1, t2), query in image_pairs:
            query = query.replace(" image", "")
            
            # Fix generic or numeric queries
            if query.isdigit() or (query.strip().replace(',', '').isdigit()):
                if self._db_main_topic:
                    query = f"{self._db_main_topic} {query}"
                else:
                    query = "car" # Generic fallback
            
            self._db_image_queries.append({"timestamp": t1, "query": query})
        
        self.logger(f"Generated {len(self._db_image_queries)} image queries for key topics")
        return self._db_image_queries

    # Add a getter method for the image queries
    def get_image_queries(self):
        """Return the generated image queries if available."""
        return getattr(self, '_db_image_queries', [])
    
    def get_video_duration(self):
        """Return the video duration if available."""
        return getattr(self, '_db_voiceover_duration', 0)

    def _generateVideoSearchTerms(self):
        self.verifyParameters(captionsTimed=self._db_timed_captions)
        # Returns a list of pairs of timing (t1,t2) + 3 search video queries, such as: [[t1,t2], [search_query_1, search_query_2, search_query_3]]
        self._db_timed_video_searches = gpt_editing.getVideoSearchQueriesTimed(self._db_timed_captions)

    def _generateVideoUrls(self):
        timed_video_searches = self._db_timed_video_searches
        self.verifyParameters(captionsTimed=timed_video_searches)
        timed_video_urls = []
        used_links = []
        for (t1, t2), search_terms in timed_video_searches:
            url = ""
            for query in reversed(search_terms):
                url = getBestVideo(query, orientation_landscape=not self._db_format_vertical, used_vids=used_links)
                if url:
                    used_links.append(url.split('.hd')[0])
                    break
            timed_video_urls.append([[t1, t2], url])
        self._db_timed_video_urls = timed_video_urls

    def _chooseBackgroundMusic(self):
        if self._db_background_music_name:
            self._db_background_music_url = AssetDatabase.get_asset_link(self._db_background_music_name)

    def _prepareBackgroundAssets(self):
        self.verifyParameters(voiceover_audio_url=self._db_audio_path)
        if not self._db_voiceover_duration:
            self.logger("Rendering short: (1/4) preparing voice asset...")
            self._db_audio_path, self._db_voiceover_duration = get_asset_duration(
                self._db_audio_path, isVideo=False)

    def _prepareCustomAssets(self):
        self.logger("Rendering short: (3/4) preparing custom assets...")
        pass

    def _editAndRenderShort(self):
        self.verifyParameters(
            voiceover_audio_url=self._db_audio_path)

        outputPath = self.dynamicAssetDir+"rendered_video.mp4"
        if not (os.path.exists(outputPath)):
            self.logger("Rendering short: Starting automated editing...")
            videoEditor = EditingEngine()
            videoEditor.addEditingStep(EditingStep.ADD_VOICEOVER_AUDIO, {
                                       'url': self._db_audio_path})
            if (self._db_background_music_url):
                videoEditor.addEditingStep(EditingStep.ADD_BACKGROUND_MUSIC, {'url': self._db_background_music_url,
                                                                              'loop_background_music': self._db_voiceover_duration,
                                                                              "volume_percentage": 0.08})
            for (t1, t2), video_url in self._db_timed_video_urls:
                videoEditor.addEditingStep(EditingStep.ADD_BACKGROUND_VIDEO, {'url': video_url,
                                                                              'set_time_start': t1,
                                                                              'set_time_end': t2})
            if (self._db_format_vertical):
                caption_type = EditingStep.ADD_CAPTION_SHORT_ARABIC if self._db_language == Language.ARABIC.value else EditingStep.ADD_CAPTION_SHORT
            else:
                caption_type = EditingStep.ADD_CAPTION_LANDSCAPE_ARABIC if self._db_language == Language.ARABIC.value else EditingStep.ADD_CAPTION_LANDSCAPE

            for (t1, t2), text in self._db_timed_captions:
                videoEditor.addEditingStep(caption_type, {'text': text.upper(),
                                                          'set_time_start': t1,
                                                          'set_time_end': t2})

            # Add image overlays before captions so they appear behind text
            if hasattr(self, '_db_image_queries') and self._db_image_queries:
                for i, query_data in enumerate(self._db_image_queries):
                    timestamp = query_data["timestamp"]
                    query = query_data["query"]
                    
                    # Use direct image URL if that's what was provided
                    if query.startswith("http"):
                        self.logger(f"[DEBUG] Query for segment at {timestamp}s: {query}")
                        videoEditor.addEditingStep(EditingStep.ADD_IMAGE, {
                            'url': query,
                            'set_time_start': timestamp,
                            'set_time_end': timestamp + 4.0
                        })
                    else:
                        # Clean up query
                        if query.isdigit() or len(query) < 3:
                            if hasattr(self, '_db_main_topic') and self._db_main_topic:
                                query = self._db_main_topic
                    
                        self.logger(f"[DEBUG] Adding image '{query}' at {timestamp}s")
                        try:
                            from shortGPT.editing_utils.editing_images import searchImageUrlsFromQuery
                            image_url = searchImageUrlsFromQuery(query)
                            
                            if image_url:
                                videoEditor.addEditingStep(EditingStep.ADD_IMAGE, {
                                    'url': image_url,
                                    'set_time_start': timestamp,
                                    'set_time_end': timestamp + 4.0
                                })
                            else:
                                self.logger(f"[WARNING] Could not find image for '{query}'")
                        except Exception as e:
                            self.logger(f"[ERROR] Failed to add image for '{query}': {str(e)}")
            else:
                self.logger("WARNING: No image queries generated. Video will not have image overlays.")
            
            # Enforce strict 30-second limit
            if hasattr(self, '_db_voiceover_duration') and self._db_voiceover_duration > 30:
                self.logger("Video exceeds 30 seconds (current: {:.1f}s). Enforcing 30 second limit.".format(self._db_voiceover_duration))
                videoEditor.addEditingStep(EditingStep.CLIP_VIDEO, {'duration': 30})
            
            videoEditor.renderVideo(outputPath, logger= self.logger if self.logger is not self.default_logger else None)

        self._db_video_path = outputPath

    def _addMetadata(self):
        if not os.path.exists('videos/'):
            os.makedirs('videos')
        self._db_yt_title, self._db_yt_description = gpt_yt.generate_title_description_dict(self._db_script)

        newFileName = f"videos/" + re.sub(r"[^a-zA-Z0-9 '\n\.]", '', self._db_yt_title)  # Removed date_str
        shutil.move(self._db_video_path, newFileName+".mp4")
        with open(newFileName+".txt", "w", encoding="utf-8") as f:
            f.write(
                f"---Youtube title---\n{self._db_yt_title}\n---Youtube description---\n{self._db_yt_description}")
        self._db_video_path = newFileName+".mp4"
        self._db_ready_to_upload = True
