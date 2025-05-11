import sys
import os
import numpy as np
import warnings
import traceback
import time
import argparse
import random
import re # Для парсинга ASS

# Игнорирование предупреждений
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import librosa 
except ImportError as e:
    print(f"Ошибка импорта librosa: {e}\nУстановите: pip install librosa")
    sys.exit(1)

try:
    import moviepy.editor as mp
    import moviepy.video.fx.all as vfx 
    from moviepy.config import get_setting # Для проверки ImageMagick
except ImportError as e:
    print(f"Ошибка импорта moviepy: {e}\nУстановите: pip install moviepy==1.0.3")
    sys.exit(1)

# --- Проверка ImageMagick при запуске ---
IMAGEMAGICK_DEFAULT_BINARY_PATH = "" # Глобальная переменная для хранения пути
try:
    IMAGEMAGICK_DEFAULT_BINARY_PATH = get_setting('IMAGEMAGICK_BINARY')
    print(f"ImageMagick Binary (MoviePy setting): {IMAGEMAGICK_DEFAULT_BINARY_PATH}")
    if not os.path.exists(IMAGEMAGICK_DEFAULT_BINARY_PATH):
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл ImageMagick не найден по пути из конфигурации: {IMAGEMAGICK_DEFAULT_BINARY_PATH}")
        print("  MoviePy может не работать корректно с TextClip.")
        IMAGEMAGICK_DEFAULT_BINARY_PATH = "" # Сбрасываем, если путь невалиден
except KeyError:
    print("ПРЕДУПРЕЖДЕНИЕ: IMAGEMAGICK_BINARY не определен в конфигурации MoviePy.")
    print("  Убедитесь, что ImageMagick установлен (с legacy utilities и добавлен в PATH).")
    print("  MoviePy может не найти ImageMagick, что вызовет проблемы с TextClip.")
    print("  Если ImageMagick установлен, но не находится, создайте moviepy/config.py")
    print("  из moviepy/config_defaults.py и укажите там IMAGEMAGICK_BINARY (например, путь к magick.exe или convert.exe).")
except Exception as e_imagick_check:
    print(f"Ошибка при проверке конфигурации ImageMagick: {e_imagick_check}")


def parse_ass_time(time_str):
    try:
        h, m, s_cs = time_str.split(':')
        s, cs = s_cs.split('.')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0
    except ValueError: print(f"Ошибка парсинга времени из ASS: '{time_str}'"); return 0.0

def parse_ass_file(filepath):
    events = []; styles = {} 
    if not os.path.exists(filepath): print(f"Файл субтитров не найден: {filepath}"); return events, styles
    dialogue_pattern = re.compile(r"Dialogue:\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*(.*)")
    in_events_section = False; in_styles_section = False; style_field_names = [] 
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith(';'): continue
                if line.lower() == "[script info]": in_events_section = False; in_styles_section = False; style_field_names = []; continue
                if line.lower() == "[events]": in_events_section = True; in_styles_section = False; style_field_names = []; continue
                if line.lower().startswith("[v4") and "styles]" in line.lower(): in_styles_section = True; in_events_section = False; style_field_names = []; continue
                if line.startswith('[') and not (in_styles_section or in_events_section): continue
                if in_styles_section and line.lower().startswith("format:"):
                    style_field_names = [field.strip().lower() for field in line.split(":", 1)[1].strip().split(',')]
                    print(f"  [DEBUG STYLE PARSING] Поля стилей ({len(style_field_names)}): {style_field_names}"); continue
                if in_styles_section and line.lower().startswith("style:") and style_field_names:
                    try:
                        style_data_part = line.split(":", 1)[1].strip(); style_values_raw = style_data_part.split(',', len(style_field_names) - 1)
                        if len(style_values_raw) >= len(style_field_names) -1 :
                            style_values = [val.strip() for val in style_values_raw]
                            if len(style_values) < len(style_field_names) and "encoding" in style_field_names: style_values.append("")
                            if len(style_values) == len(style_field_names):
                                style_dict_raw = dict(zip(style_field_names, style_values))
                                style_name_key = next((key for key in style_dict_raw if key.lower() == 'name'), None)
                                style_name = style_dict_raw.get(style_name_key, f"S{len(styles)}").strip() if style_name_key else f"S{len(styles)}"
                                if not style_name: style_name = f"S{len(styles)}"
                                def safe_float(s,d=0.0): return float(s.strip()) if s and s.strip() else d
                                def safe_int(s,d=0): return int(s.strip()) if s and s.strip() else d
                                styles[style_name] = {"fontname": style_dict_raw.get("fontname", "Arial").strip(), "fontsize": safe_float(style_dict_raw.get("fontsize"), 40),
                                    "primarycolour": style_dict_raw.get("primarycolour", "&H00FFFFFF").strip(), "outlinecolour": style_dict_raw.get("outlinecolour", "&H00000000").strip(),
                                    "backcolour": style_dict_raw.get("backcolour", "&H00000000").strip(), "bold": style_dict_raw.get("bold", "0").strip() in ['-1', '1'],
                                    "italic": style_dict_raw.get("italic", "0").strip() in ['-1', '1'], "underline": style_dict_raw.get("underline", "0").strip() in ['-1', '1'],
                                    "strikeout": style_dict_raw.get("strikeout", "0").strip() in ['-1', '1'], "borderstyle": safe_int(style_dict_raw.get("borderstyle"), 1),
                                    "outline": safe_float(style_dict_raw.get("outline"), 0), "shadow": safe_float(style_dict_raw.get("shadow"), 0),    
                                    "alignment": safe_int(style_dict_raw.get("alignment"), 2),}
                                print(f"    [DEBUG STYLE PARSING] Стиль '{style_name}': Font='{styles[style_name]['fontname']}', Size={styles[style_name]['fontsize']}")
                            else: print(f"  Предупреждение: Несовпадение полей ({len(style_values)}) и заголовков ({len(style_field_names)}) в стиле (строка {line_num}): {line}")
                        else: print(f"  Предупреждение: Не удалось разделить строку стиля (строка {line_num}): {line}")
                    except Exception as e: print(f"  Ошибка парсинга строки стиля (строка {line_num}) '{line}': {e}")
                elif in_events_section and line.lower().startswith("dialogue:"):
                    match = dialogue_pattern.match(line); 
                    if match:
                        g = match.groups()
                        try:
                            s, e_time, style, text = parse_ass_time(g[1]), parse_ass_time(g[2]), g[3].strip(), g[9]
                            if e_time > s : events.append({"start": s, "end": e_time, "duration": e_time - s, "style_name": style, "text": text})
                        except Exception as e: print(f"Ошибка парсинга диалога (строка {line_num}) '{line}': {e}")
    except Exception as e: print(f"Критическая ошибка чтения файла '{filepath}': {e}"); traceback.print_exc()
    events.sort(key=lambda x: x["start"])
    if styles: print(f"Успешно загружено {len(styles)} стилей.")
    else: print("Стили не загружены."); 
    return events, styles

def ass_color_to_rgb_tuple(c):
    if not isinstance(c, str) or not c.startswith('&H'): return (255,255,255) 
    h = c[2:].upper(); 
    try: 
        if len(h)==8: return (int(h[6:8],16),int(h[4:6],16),int(h[2:4],16))
        if len(h)==6: return (int(h[4:6],16),int(h[2:4],16),int(h[0:2],16))
    except: pass
    return (255,255,255)

def get_ass_alignment(a):
    tA='center'; pS={1:('left','bottom'),2:('center','bottom'),3:('right','bottom'),4:('left','center'),5:('center','center'),6:('right','center'),7:('left','top'),8:('center','top'),9:('right','top')}.get(a,('center','bottom'))
    if a in [1,4,7]:tA='west'; 
    if a in [3,6,9]:tA='east'; 
    return tA, pS

def create_montage_from_subs_cli(
    available_video_files_paths, audio_filepath, subtitle_ass_file, output_filepath,
    max_allowed_duration=0, min_allowed_duration=0
):
    print(f"--- Монтаж по субтитрам --- Файл: {subtitle_ass_file}, Аудио: {audio_filepath}") # Сокращенный принт
    subtitle_events, ass_styles = parse_ass_file(subtitle_ass_file)
    if not subtitle_events: print("Ошибка: Нет событий субтитров."); return False
    source_video_clips_info = []
    for p in available_video_files_paths:
        try:
            with mp.VideoFileClip(p) as tc: d,f,s = tc.duration,tc.fps,tc.size
            if d and d > 0.1: source_video_clips_info.append({"path":p,"duration":d,"fps":f if f and f>0 else 24.0,"size":s})
        except: print(f"Предупреждение: Не удалось загрузить {os.path.basename(p)}.");
    if not source_video_clips_info: print("Ошибка: Нет видео для монтажа."); return False
    
    main_audio_clip = None; opened_clips = {}; vid_segs = []; txt_segs = []
    base_vid_comp = None; vid_w_audio = None; final_comp = None
    try:
        main_audio_clip = mp.AudioFileClip(audio_filepath)
        target_fps, target_size = source_video_clips_info[0]["fps"], source_video_clips_info[0]["size"]
        print(f"Цель: FPS={target_fps}, Размер={target_size}")
        montage_time = 0.0
        for idx, sub_e in enumerate(subtitle_events):
            seg_dur, seg_start = sub_e["duration"], sub_e["start"]
            if max_allowed_duration and seg_start >= max_allowed_duration: print(f"Макс.длит {max_allowed_duration}s"); break
            if max_allowed_duration and seg_start + seg_dur > max_allowed_duration: seg_dur = max_allowed_duration - seg_start
            if seg_dur <= 0.02: continue
            
            vid_info = random.choice(source_video_clips_info); vid_path = vid_info["path"]
            try:
                if vid_path not in opened_clips:
                    cl = mp.VideoFileClip(vid_path, target_resolution=(target_size[1],target_size[0]), fps_source="fps")
                    if not cl.fps or cl.fps<=0: cl.fps=target_fps
                    if cl.size[0]!=target_size[0] or cl.size[1]!=target_size[1]: cl=cl.resize(width=target_size[0],height=target_size[1])
                    opened_clips[vid_path]=cl
                src_cl = opened_clips[vid_path]
                max_s = vid_info["duration"] - seg_dur
                v_seg = src_cl.subclip(0,vid_info["duration"]).set_duration(seg_dur) if max_s<0 and vid_info["duration"]>=0.1 else (src_cl.subclip(random.uniform(0,max_s),random.uniform(0,max_s)+seg_dur) if max_s>=0 else None)
                if not v_seg: continue
                if not v_seg.fps: v_seg.fps=target_fps
                vid_segs.append(v_seg.set_start(seg_start).set_duration(seg_dur))
            except Exception as e: print(f"Ошибка видео-сегмента из {os.path.basename(vid_path)}: {e}")
            
            try: # ТЕКСТОВЫЙ КЛИП
                style_name = sub_e["style_name"]; style = ass_styles.get(style_name, ass_styles.get("Default",{}))
                if not style and style_name!="Default": style=ass_styles.get("Default",{})
                if not style: print(f"Предупреждение: Стили '{style_name}' и 'Default' не найдены.")
                
                font = style.get("fontname","Arial"); size_f = int(style.get("fontsize",40)); color_t = ass_color_to_rgb_tuple(style.get("primarycolour","&H00FFFFFF"))
                
                txt = re.sub(r"\{[^}]*\}","",sub_e["text"])
                if not txt.strip(): 
                    if sub_e["text"].strip(): print(f"Текст @ {seg_start:.2f}s был из тегов. Пропуск.")
                    montage_time = max(montage_time, seg_start + seg_dur); continue
                
                print(f"  TextClip: '{txt[:20]}...', Font='{font}', Size={size_f}, Color={color_t}")
                tc_inst = None
                try:
                    current_imagemagick_binary = IMAGEMAGICK_DEFAULT_BINARY_PATH
                    if not current_imagemagick_binary or not os.path.exists(current_imagemagick_binary):
                        print("ОШИБКА: Путь к ImageMagick недействителен или не найден. TextClip не будет создан.")
                        raise FileNotFoundError(f"ImageMagick не найден или путь невалиден: {current_imagemagick_binary}")

                    print(f"  [DEBUG TextClip] Используется ImageMagick: {current_imagemagick_binary}")
                    tc_inst = mp.TextClip(txt=txt, 
                                          font=font, 
                                          fontsize=size_f, 
                                          color=color_t,
                                          imagemagick_binary=current_imagemagick_binary
                                          )
                    print(f"    TextClip создан успешно.")
                except Exception as e_tc: 
                    print(f"    Ошибка TextClip: {e_tc}")
                    traceback.print_exc() # Печатаем полный трейсбек ошибки TextClip
                    montage_time = max(montage_time, seg_start + seg_dur); continue 
                
                if tc_inst:
                    _,txt_pos_default = get_ass_alignment(style.get("alignment", 2))
                    tc_inst=tc_inst.set_duration(seg_dur).set_start(seg_start).set_position(txt_pos_default)
                    txt_segs.append(tc_inst)
            except Exception as e: print(f"Ошибка блока текста: {e}"); traceback.print_exc()
            montage_time = max(montage_time, seg_start + seg_dur)

        if min_allowed_duration and montage_time < min_allowed_duration: print(f"Ошибка: Длит. ({montage_time:.2f}s) < мин. ({min_allowed_duration}s)."); return False
        if not vid_segs: print("Ошибка: Нет видео-сегментов."); return False
        print(f"Событий: {idx+1 if subtitle_events else 0}. Длит. монтажа: {montage_time:.2f}s")

        valid_vs = [vs for vs in vid_segs if vs and vs.duration and vs.duration>0]
        if not valid_vs: print("Ошибка: Нет валидных видеосегментов."); return False
        base_vid_comp = mp.CompositeVideoClip(valid_vs,size=target_size,bg_color=(0,0,0)).set_duration(montage_time)
        if not base_vid_comp.fps: base_vid_comp.fps=target_fps
        
        audio_final = main_audio_clip.subclip(0,montage_time)
        if montage_time > main_audio_clip.duration:
            audio_final = mp.concatenate_audioclips([main_audio_clip]*(int(montage_time/main_audio_clip.duration)+1)).subclip(0,montage_time)
        vid_w_audio = base_vid_comp.set_audio(audio_final)

        final_render_clips = [vid_w_audio] + txt_segs
        final_comp = mp.CompositeVideoClip(final_render_clips,size=target_size,bg_color=(0,0,0)).set_duration(montage_time)
        if not final_comp.fps: final_comp.fps=target_fps

        print(f"Сохранение: {output_filepath}, FPS: {final_comp.fps or target_fps}")
        final_comp.write_videofile(output_filepath,codec='libx264',fps=(final_comp.fps or target_fps),threads=max(1,os.cpu_count()//2 if os.cpu_count() else 2),preset='ultrafast',audio_codec='aac',audio_bitrate='192k',logger='bar')
        print(f"Сохранено: {output_filepath}"); return True
    except Exception as e: print(f"Крит. ошибка монтажа: {e}"); traceback.print_exc(); return False
    finally:
        print("Освобождение ресурсов...")
        res_list=[main_audio_clip,base_vid_comp,vid_w_audio,final_comp]+list(opened_clips.values())+vid_segs+txt_segs
        for cl_obj in res_list:
            if cl_obj and hasattr(cl_obj,'close'):
                try:
                    if hasattr(cl_obj,'reader') and cl_obj.reader: cl_obj.close()
                    elif not hasattr(cl_obj,'reader'): cl_obj.close()
                except:pass
        print("Ресурсы освобождены.")

def find_files(directory, extensions):
    found_files = []
    if directory and os.path.isdir(directory):
        for f_name in os.listdir(directory):
            if any(f_name.lower().endswith(ext.lower()) for ext in extensions):
                found_files.append(os.path.join(directory, f_name))
    return found_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Создает видеомонтажи по файлу субтитров.")
    parser.add_argument("-vd", "--video_dir", required=True, help="Папка с исходными видеофайлами.")
    parser.add_argument("-ad", "--audio_dir", required=True, help="Папка с аудиофайлами для фона.")
    parser.add_argument("-sub", "--subtitle_ass_file", required=True, help="Путь к файлу субтитров .ASS.")
    parser.add_argument("-od", "--output_dir", required=True, help="Папка для сохранения.")
    parser.add_argument("-n", "--num_montages", type=int, default=1, help="Количество монтажей.")
    parser.add_argument("-max_dur", "--max_duration", type=int, default=0, help="Макс. длительность (сек, 0=без огр.).")
    parser.add_argument("-min_dur", "--min_duration", type=int, default=0, help="Мин. длительность (сек, 0=нет проверки).")
    
    args = parser.parse_args()

    if not os.path.isdir(args.video_dir): sys.exit(f"Ошибка: Папка видео не найдена: {args.video_dir}")
    if not os.path.isdir(args.audio_dir): sys.exit(f"Ошибка: Папка аудио не найдена: {args.audio_dir}")
    if not os.path.exists(args.subtitle_ass_file): sys.exit(f"Ошибка: Файл субтитров не найден: {args.subtitle_ass_file}")
    if not os.path.exists(args.output_dir):
        try: os.makedirs(args.output_dir); print(f"Создана директория: {args.output_dir}")
        except Exception as e: sys.exit(f"Ошибка создания директории '{args.output_dir}': {e}")

    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    audio_extensions = ['.mp3', '.wav', '.aac', '.ogg', '.flac']

    all_input_video_files = find_files(args.video_dir, video_extensions)
    all_input_audio_files = find_files(args.audio_dir, audio_extensions)

    if not all_input_video_files: sys.exit(f"Видеофайлы не найдены в {args.video_dir}")
    if not all_input_audio_files: sys.exit(f"Аудиофайлы не найдены в {args.audio_dir}")

    print(f"Найдено видео: {len(all_input_video_files)}, аудио: {len(all_input_audio_files)}")
    
    processed_montages = 0; total_start_time = time.time()

    for i in range(args.num_montages):
        print(f"\n--- Создание видеомонтажа #{i+1}/{args.num_montages} (по субтитрам) ---")
        chosen_audio_for_montage = random.choice(all_input_audio_files)
        print(f"Аудио для монтажа #{i+1}: {os.path.basename(chosen_audio_for_montage)}")

        audio_basename = os.path.splitext(os.path.basename(chosen_audio_for_montage))[0]
        subs_basename = os.path.splitext(os.path.basename(args.subtitle_ass_file))[0]
        timestamp_str = time.strftime("%H%M%S")
        output_filename = f"montage_subs_{subs_basename}_audio_{audio_basename}_{timestamp_str}_{i+1}.mp4"
        output_filepath = os.path.join(args.output_dir, output_filename)
        
        single_montage_start_time = time.time()
        success = create_montage_from_subs_cli(
            all_input_video_files, chosen_audio_for_montage, args.subtitle_ass_file,
            output_filepath, max_allowed_duration=args.max_duration, min_allowed_duration=args.min_duration
        )
        single_montage_end_time = time.time()

        if success: processed_montages +=1; print(f"Монтаж #{i+1} создан за {single_montage_end_time - single_montage_start_time:.2f} сек.")
        else: print(f"Ошибка создания монтажа #{i+1}.")

    total_end_time = time.time()
    print(f"\n--- Завершено ---")
    print(f"Успешно создано: {processed_montages} из {args.num_montages}. Общее время: {total_end_time - total_start_time:.2f} сек.")