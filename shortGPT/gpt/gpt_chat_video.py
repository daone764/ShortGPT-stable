from shortGPT.gpt import gpt_utils
import json
def generateScript(script_description, language):
    out = {'script': ''}
    chat, system = gpt_utils.load_local_yaml_prompt('chat_video_script')
    chat = chat.replace("<<DESCRIPTION>>", script_description).replace("<<LANGUAGE>>", language)
    while not ('script' in out and out['script']):
        try:
            result = gpt_utils.llm_completion(chat_prompt=chat, system=system, temp=1)
            out = json.loads(result)
        except Exception as e:
            print(e, "Difficulty parsing the output in gpt_chat_video.generateScript")
    return out['script']

def correctScript(script, correction):
    out = {'script': ''}
    chat, system = gpt_utils.load_local_yaml_prompt('chat_video_edit_script')
    chat = chat.replace("<<ORIGINAL_SCRIPT>>", script).replace("<<CORRECTIONS>>", correction)

    while not ('script' in out and out['script']):
        try:
            result = gpt_utils.llm_completion(chat_prompt=chat, system=system, temp=1)
            out = json.loads(result)
        except Exception as e:
            print("Difficulty parsing the output in gpt_chat_video.generateScript")
    return out['script']

def generateFactsScript(script_description, language="English"):
    from pathlib import Path
    import yaml
    
    # Load the YAML file directly since load_local_yaml_prompt is having issues
    _here = Path(__file__).parent
    _absolute_path = (_here / '..' / 'prompt_templates' / 'facts_generator.yaml').resolve()
    
    with open(_absolute_path, 'r', encoding='utf-8') as f:
        json_template = yaml.safe_load(f)
    
    chat = json_template['chat_prompt']
    system = json_template['system_prompt']
    
    chat = chat.replace("<<FACTS_TYPE>>", script_description)
    
    # Since facts_generator returns plain text, not JSON, we directly return it
    result = gpt_utils.llm_completion(chat_prompt=chat, system=system, temp=1)
    return result