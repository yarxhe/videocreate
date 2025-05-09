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
    import librosa # Хотя и не используется для нарезки, оставим для возможного анализа музыки
except ImportError as e:
    print(f"Ошибка импорта librosa: {e}\nУстановите: pip install librosa")
    sys.exit(1)

try:
    import moviepy.editor as mp
    import moviepy.video.fx.all as vfx # Для возможных эффектов в будущем
except ImportError as e:
    print(f"Ошибка импорта moviepy: {e}\nУстановите: pip install moviepy")
    sys.exit(1)

def parse_ass_time(time_str):
    try:
        h, m, s_cs = time_str.split(':')
        s, cs = s_cs.split('.')
        # В ASS сотые доли секунды, поэтому cs (centiseconds)
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0
    except ValueError:
        print(f"Ошибка парсинга времени из ASS: '{time_str}'")
        return 0.0

def parse_ass_file(filepath):
    events = []
    styles = {} # Для хранения стилей
    if not os.path.exists(filepath):
        print(f"Файл субтитров не найден: {filepath}")
        return events, styles # Возвращаем пустые события и стили
        
    dialogue_pattern = re.compile(r"Dialogue:\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*(.*)")
    style_pattern = re.compile(r"Style:\s*([^,]+),\s*([^,]*),\s*([^,]*),\s*(&H[0-9A-Fa-f]{8}|&H[0-9A-Fa-f]{6}),\s*(&H[0-9A-Fa-f]{8}|&H[0-9A-Fa-f]{6}),\s*(&H[0-9A-Fa-f]{8}|&H[0-9A-Fa-f]{6}),\s*(&H[0-9A-Fa-f]{8}|&H[0-9A-Fa-f]{6}),\s*([01-]),\s*([01-]),\s*([01-]),\s*([01-]),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*)")
    # Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

    in_events_section = False
    in_styles_section = False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';'): continue # Пропускаем пустые строки и комментарии

                if line == "[Events]":
                    in_events_section = True
                    in_styles_section = False
                    continue
                if line == "[V4+ Styles]":
                    in_styles_section = True
                    in_events_section = False
                    continue
                if line.startswith('['): # Начало другой секции
                    in_events_section = False
                    in_styles_section = False
                    continue
                
                if in_styles_section and line.startswith("Style:"):
                    match = style_pattern.match(line)
                    if match:
                        groups = match.groups()
                        styles[groups[0].strip()] = { # Name
                            "fontname": groups[1].strip(),
                            "fontsize": float(groups[2].strip()) if groups[2].strip() else 70,
                            "primary_colour": groups[3].strip(), # &HAABBGGRR
                            # "secondary_colour": groups[4].strip(), # Для караоке
                            "outline_colour": groups[5].strip(),
                            "back_colour": groups[6].strip(), # Тень
                            "bold": groups[7].strip() == '-1' or groups[7].strip() == '1',
                            "italic": groups[8].strip() == '-1' or groups[8].strip() == '1',
                            "underline": groups[9].strip() == '-1' or groups[9].strip() == '1',
                            "strikeout": groups[10].strip() == '-1' or groups[10].strip() == '1',
                            "border_style": int(groups[15].strip()) if groups[15].strip() else 1,
                            "outline_width": float(groups[16].strip()) if groups[16].strip() else 0, # Outline thickness
                            "shadow_depth": float(groups[17].strip()) if groups[17].strip() else 0, # Shadow distance
                            "alignment": int(groups[18].strip()) if groups[18].strip() else 2, # Numpad alignment
                        }

                elif in_events_section and line.startswith("Dialogue:"):
                    match = dialogue_pattern.match(line)
                    if match:
                        groups = match.groups()
                        try:
                            start_time = parse_ass_time(groups[1])
                            end_time = parse_ass_time(groups[2])
                            style_name = groups[3].strip()
                            text = groups[9]
                            # Пропускаем строки без текста или с нулевой длительностью
                            if end_time > start_time and text.strip():
                                events.append({
                                    "start": start_time, "end": end_time,
                                    "duration": end_time - start_time,
                                    "style_name": style_name, "text": text
                                })
                        except Exception as e_parse_dialogue:
                            print(f"Ошибка парсинга строки диалога '{line}': {e_parse_dialogue}")
    except Exception as e_open_file:
        print(f"Ошибка чтения файла субтитров '{filepath}': {e_open_file}")

    events.sort(key=lambda x: x["start"])
    return events, styles

def ass_color_to_rgb_tuple(ass_color_str):
    # &HAABBGGRR -> (R, G, B), alpha игнорируется для цвета MoviePy
    # MoviePy TextClip color ожидает 'red', '#FF0000', or (R,G,B)
    if ass_color_str.startswith('&H'):
        hex_color = ass_color_str[2:]
        if len(hex_color) == 8: # AABBGGRR
            # alpha = int(hex_color[0:2], 16) # Не используется напрямую в color
            blue = int(hex_color[2:4], 16)
            green = int(hex_color[4:6], 16)
            red = int(hex_color[6:8], 16)
            return (red, green, blue)
        elif len(hex_color) == 6: # BBGGRR (без альфы)
            blue = int(hex_color[0:2], 16)
            green = int(hex_color[2:4], 16)
            red = int(hex_color[4:6], 16)
            return (red, green, blue)
    return (255, 255, 255) # Default to white if parsing fails

def get_ass_alignment(align_val):
    # Numpad alignment to MoviePy position string
    # 1: bottom-left, 2: bottom-center, 3: bottom-right
    # 4: middle-left, 5: middle-center, 6: middle-right
    # 7: top-left,    8: top-center,    9: top-right
    positions = {
        1: ('left', 'bottom'), 2: ('center', 'bottom'), 3: ('right', 'bottom'),
        4: ('left', 'center'), 5: ('center', 'center'), 6: ('right', 'center'),
        7: ('left', 'top'),    8: ('center', 'top'),    9: ('right', 'top')
    }
    return positions.get(align_val, ('center', 'bottom')) # Default to bottom-center


def create_montage_from_subs_cli(
    available_video_files_paths,
    audio_filepath,
    subtitle_ass_file,
    output_filepath,
    max_allowed_duration=0,
    min_allowed_duration=0
    # transition_type='none', # Переходы пока не добавляем для этой логики
    # transition_duration_secs=0.3
):
    print("--- Начало создания видеомонтажа по субтитрам ---")
    print(f"  Файл субтитров (ASS): {subtitle_ass_file}")
    print(f"  Аудио для фона: {audio_filepath}")
    print(f"  Выходной файл: {output_filepath}")

    subtitle_events, ass_styles = parse_ass_file(subtitle_ass_file)
    if not subtitle_events:
        print("Ошибка: Нет событий субтитров для обработки.")
        return False
    print(f"Загружено {len(subtitle_events)} событий субтитров и {len(ass_styles)} стилей.")

    source_video_clips_info = []
    for vf_path in available_video_files_paths:
        try:
            with mp.VideoFileClip(vf_path) as temp_clip:
                duration = temp_clip.duration; fps = temp_clip.fps; size = temp_clip.size
                if duration is not None and duration > 0.1:
                     source_video_clips_info.append({"path": vf_path, "duration": duration, "fps": fps if fps and fps > 0 else 24.0, "size": size})
                else: print(f"Предупреждение: Видео {os.path.basename(vf_path)} имеет недостаточную длительность/FPS. Пропуск.")
        except Exception as e: print(f"Предупреждение: Не удалось загрузить {os.path.basename(vf_path)}: {e}. Пропуск.")
    if not source_video_clips_info: print("Ошибка: Нет доступных видеофайлов для монтажа."); return False

    main_audio_clip = None
    opened_source_video_clips = {} 
    video_segments_for_montage = []
    text_clips_for_montage = []    
    
    # Промежуточные клипы для корректного закрытия
    base_video_layer_composite = None
    video_with_audio = None
    final_output_composite_clip = None

    try:
        main_audio_clip = mp.AudioFileClip(audio_filepath)
        
        # Определяем общий размер и FPS для монтажа (по первому видео или можно сделать параметром)
        # Важно, чтобы все TextClip создавались под этот размер.
        target_fps = source_video_clips_info[0]["fps"]
        target_size = source_video_clips_info[0]["size"]
        print(f"Целевой FPS для монтажа: {target_fps}, Целевой размер: {target_size}")

        current_montage_end_time = 0.0 # Время окончания последнего добавленного сегмента

        for event_idx, sub_event in enumerate(subtitle_events):
            segment_duration = sub_event["duration"]
            segment_start_in_montage = sub_event["start"]

            if max_allowed_duration > 0 and segment_start_in_montage >= max_allowed_duration:
                print(f"Достигнута макс. длительность {max_allowed_duration}s. Остановка обработки субтитров.")
                break
            
            if max_allowed_duration > 0 and segment_start_in_montage + segment_duration > max_allowed_duration:
                segment_duration = max_allowed_duration - segment_start_in_montage
                print(f"  Событие субтитра #{event_idx} обрезано до {segment_duration:.2f}s из-за max_allowed_duration.")
            
            if segment_duration <= 0.02: continue

            # --- Создание видеосегмента ---
            chosen_video_info = random.choice(source_video_clips_info)
            source_video_path = chosen_video_info["path"]
            
            try:
                if source_video_path not in opened_source_video_clips:
                    clip_obj = mp.VideoFileClip(source_video_path, target_resolution=(target_size[1], target_size[0]), fps_source="fps")
                    if clip_obj.fps is None or clip_obj.fps <= 0: clip_obj.fps = target_fps
                    if clip_obj.size[0] != target_size[0] or clip_obj.size[1] != target_size[1]:
                        clip_obj = clip_obj.resize(width=target_size[0], height=target_size[1])
                    opened_source_video_clips[source_video_path] = clip_obj
                source_clip_instance = opened_source_video_clips[source_video_path]

                max_start_in_src = chosen_video_info["duration"] - segment_duration
                video_sub_segment = None
                if max_start_in_src < 0:
                    if chosen_video_info["duration"] >= 0.1:
                        video_sub_segment = source_clip_instance.subclip(0, chosen_video_info["duration"]).set_duration(segment_duration) # Растягиваем/обрезаем до нужной длины
                        print(f"  Видео {os.path.basename(source_video_path)} ({chosen_video_info['duration']:.2f}s) изменено до ({segment_duration:.2f}s).")
                    else: continue
                else:
                    rand_start = random.uniform(0, max_start_in_src)
                    video_sub_segment = source_clip_instance.subclip(rand_start, rand_start + segment_duration)
                
                if video_sub_segment.fps is None: video_sub_segment.fps = target_fps
                video_sub_segment = video_sub_segment.set_start(segment_start_in_montage).set_duration(segment_duration) # Гарантируем длительность
                video_segments_for_montage.append(video_sub_segment)
                print(f"  Видео-сегмент: {video_sub_segment.duration:.2f}s из {os.path.basename(source_video_path)} @ {segment_start_in_montage:.2f}s.")

            except Exception as e_vid_seg:
                print(f"Ошибка при создании видео-сегмента из {os.path.basename(source_video_path)}: {e_vid_seg}")
            
            # --- Создание текстового клипа (субтитра) ---
            try:
                style_to_apply = ass_styles.get(sub_event["style_name"], ass_styles.get("Default", {})) # Берем стиль события или Default
                
                font = style_to_apply.get("fontname", "Arial")
                fontsize = int(style_to_apply.get("fontsize", 40))
                color_rgb = ass_color_to_rgb_tuple(style_to_apply.get("primary_colour", "&H00FFFFFF")) # Белый по умолчанию
                # bg_color_rgb_alpha = ... # Для фона, если он есть в стиле
                outline_color_rgb = ass_color_to_rgb_tuple(style_to_apply.get("outline_colour", "&H00000000"))
                stroke_width = style_to_apply.get("outline_width", 1.5 if style_to_apply.get("border_style") == 1 else 0)
                # MoviePy TextClip не поддерживает тень напрямую как в ASS, но можно имитировать
                
                # Очистка текста от ASS тегов (очень упрощенная)
                clean_text = re.sub(r"\{[^}]*\}", "", sub_event["text"]) 
                if not clean_text.strip(): # Если после очистки текст пустой, не создаем клип
                    print(f"  Пропущен пустой текстовый клип @ {segment_start_in_montage:.2f}s.")
                    current_montage_end_time = max(current_montage_end_time, segment_start_in_montage + segment_duration)
                    continue


                text_clip = mp.TextClip(clean_text, 
                                        font=font, fontsize=fontsize, color=color_rgb,
                                        stroke_color=outline_color_rgb, stroke_width=stroke_width,
                                        method='caption', # Хорошо для переносов строк
                                        align=get_ass_alignment(style_to_apply.get("alignment", 2))[0], # 'west', 'center', 'east'
                                        size=(target_size[0]*0.95, None) # Ширина 95%, высота авто
                                        )
                text_clip = text_clip.set_duration(segment_duration)
                text_clip = text_clip.set_start(segment_start_in_montage)
                text_clip = text_clip.set_position(get_ass_alignment(style_to_apply.get("alignment", 2)))
                
                text_clips_for_montage.append(text_clip)
                print(f"  Текст-клип: \"{clean_text[:30]}...\" @ {segment_start_in_montage:.2f}s, длит: {segment_duration:.2f}s.")
            except Exception as e_txt_clip:
                print(f"Ошибка при создании текстового клипа для \"{sub_event['text'][:30]}...\": {e_txt_clip}")
            
            current_montage_end_time = max(current_montage_end_time, segment_start_in_montage + segment_duration)

        if min_allowed_duration > 0 and current_montage_end_time < min_allowed_duration:
            print(f"Ошибка: Итоговая длительность монтажа ({current_montage_end_time:.2f}s) меньше мин. ({min_allowed_duration}s).")
            return False
        if not video_segments_for_montage:
            print("Ошибка: Не создано видео-сегментов для монтажа.")
            return False

        print(f"Обработано {len(subtitle_events)} событий. Общая длительность монтажа: {current_montage_end_time:.2f}s")

        # Сборка видеоряда
        # Убедимся, что все видеосегменты имеют корректную длительность и не None
        valid_video_segments = [vs for vs in video_segments_for_montage if vs and vs.duration is not None and vs.duration > 0]
        if not valid_video_segments:
            print("Ошибка: Нет валидных видеосегментов после обработки.")
            return False

        base_video_layer_composite = mp.CompositeVideoClip(valid_video_segments, size=target_size).set_duration(current_montage_end_time)
        if base_video_layer_composite.fps is None: base_video_layer_composite.fps = target_fps

        # Наложение музыки
        if current_montage_end_time > main_audio_clip.duration:
            print(f"Предупреждение: Музыка ({main_audio_clip.duration:.2f}s) короче монтажа ({current_montage_end_time:.2f}s).")
            # Повторим музыку, если она короче
            num_loops = int(current_montage_end_time / main_audio_clip.duration) + 1
            looped_audio_clips = [main_audio_clip] * num_loops
            final_audio_for_montage = mp.concatenate_audioclips(looped_audio_clips).subclip(0, current_montage_end_time)
            # Закрываем промежуточные клипы для зацикливания, если они создавались
            for lac in looped_audio_clips:
                if lac != main_audio_clip and hasattr(lac, 'close'): lac.close() # Закрываем только копии, если они создавались
        else:
            final_audio_for_montage = main_audio_clip.subclip(0, current_montage_end_time)
        
        video_with_audio = base_video_layer_composite.set_audio(final_audio_for_montage)

        # Наложение всех текстовых клипов
        final_clips_to_render = [video_with_audio] + text_clips_for_montage
        final_output_composite_clip = mp.CompositeVideoClip(final_clips_to_render, size=target_size).set_duration(current_montage_end_time)
        if final_output_composite_clip.fps is None: final_output_composite_clip.fps = target_fps

        print(f"Начало сохранения видеомонтажа в: {output_filepath} с FPS: {final_output_composite_clip.fps or target_fps}")
        final_output_composite_clip.write_videofile(
            output_filepath, codec='libx264', fps=(final_output_composite_clip.fps or target_fps), 
            threads=max(1, os.cpu_count() // 2 if os.cpu_count() else 2), preset='ultrafast', 
            audio_codec='aac', audio_bitrate='192k', logger='bar' 
        )
        print(f"Видеомонтаж успешно сохранен: {output_filepath}")
        return True

    except Exception as e:
        print(f"Критическая ошибка в процессе создания монтажа: {e}")
        print(traceback.format_exc())
        return False
    finally:
        print("Освобождение ресурсов...")
        # ... (Блок finally для закрытия main_audio_clip, opened_source_video_clips, 
        # video_segments_for_montage, text_clips_for_montage, 
        # base_video_layer_composite, video_with_audio, final_output_composite_clip) ...
        # Важно аккуратно закрывать все созданные объекты MoviePy.
        # Код для finally из предыдущего полного скрипта должен подойти с небольшими адаптациями.
        # Я добавлю его сюда для полноты.
        if main_audio_clip and hasattr(main_audio_clip, 'close'): 
            try: main_audio_clip.close()
            except: pass
        
        for clip in opened_source_video_clips.values():
            if hasattr(clip, 'close'): 
                try: clip.close()
                except: pass
        
        for clip_list in [video_segments_for_montage, text_clips_for_montage]:
            for clip_obj in clip_list:
                if clip_obj and hasattr(clip_obj, 'close'):
                    try: clip_obj.close()
                    except: pass
        
        clips_to_close_at_end = [base_video_layer_composite, video_with_audio, final_output_composite_clip]
        for clip_obj in clips_to_close_at_end:
            if clip_obj and hasattr(clip_obj, 'close'):
                try:
                    # Проверка на reader актуальна в основном для VideoFileClip и его производных
                    if hasattr(clip_obj, 'reader') and clip_obj.reader is not None: clip_obj.close()
                    elif not hasattr(clip_obj, 'reader'): clip_obj.close() # Для CompositeVideoClip и TextClip
                except Exception: pass
        print("Ресурсы должны быть освобождены.")


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
    parser.add_argument("-sub", "--subtitle_ass_file", required=True, help="Путь к файлу субтитров .ASS, задающему структуру.")
    parser.add_argument("-od", "--output_dir", required=True, help="Папка для сохранения созданных видеомонтажей.")
    parser.add_argument(
        "-n", "--num_montages", type=int, default=1,
        help="Количество видеомонтажей для создания."
    )
    parser.add_argument(
        "-max_dur", "--max_duration", type=int, default=0,
        help="Максимальная длительность одного монтажа в секундах (0 - до конца субтитров)."
    )
    parser.add_argument(
        "-min_dur", "--min_duration", type=int, default=0,
        help="Минимальная требуемая длительность одного монтажа в секундах (0 - нет проверки)."
    )
    # Убраны аргументы для beat_tightness, transition_type, transition_duration, т.к. ритм от субтитров
    
    args = parser.parse_args()

    if not os.path.isdir(args.video_dir): sys.exit(f"Ошибка: Папка с видео не найдена: {args.video_dir}")
    if not os.path.isdir(args.audio_dir): sys.exit(f"Ошибка: Папка с аудио не найдена: {args.audio_dir}")
    if not os.path.exists(args.subtitle_ass_file): sys.exit(f"Ошибка: Файл субтитров .ASS не найден: {args.subtitle_ass_file}")
    if not os.path.exists(args.output_dir):
        try:
            os.makedirs(args.output_dir)
            print(f"Создана директория для вывода: {args.output_dir}")
        except Exception as e:
            sys.exit(f"Ошибка: Не удалось создать директорию для вывода '{args.output_dir}': {e}")

    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    audio_extensions = ['.mp3', '.wav', '.aac', '.ogg', '.flac']

    all_input_video_files = find_files(args.video_dir, video_extensions)
    all_input_audio_files = find_files(args.audio_dir, audio_extensions)

    if not all_input_video_files: sys.exit(f"Видеофайлы не найдены в {args.video_dir}")
    if not all_input_audio_files: sys.exit(f"Аудиофайлы не найдены в {args.audio_dir}")

    print(f"Найдено исходных видеофайлов: {len(all_input_video_files)}")
    print(f"Найдено исходных аудиофайлов: {len(all_input_audio_files)}")
    
    processed_montages = 0
    total_start_time = time.time()

    for i in range(args.num_montages):
        print(f"\n--- Создание видеомонтажа #{i+1}/{args.num_montages} (по субтитрам) ---")
        
        chosen_audio_for_montage = random.choice(all_input_audio_files)
        print(f"Для монтажа #{i+1} будет использоваться аудио: {os.path.basename(chosen_audio_for_montage)}")

        audio_basename = os.path.splitext(os.path.basename(chosen_audio_for_montage))[0]
        subs_basename = os.path.splitext(os.path.basename(args.subtitle_ass_file))[0]
        timestamp_str = time.strftime("%H%M%S")
        output_filename = f"montage_subs_{subs_basename}_audio_{audio_basename}_{timestamp_str}_{i+1}.mp4"
        output_filepath = os.path.join(args.output_dir, output_filename)
        
        single_montage_start_time = time.time()
        success = create_montage_from_subs_cli(
            all_input_video_files,
            chosen_audio_for_montage,
            args.subtitle_ass_file,
            output_filepath,
            # 10, # beat_tightness пока не передаем
            max_allowed_duration=args.max_duration,
            min_allowed_duration=args.min_duration
            # transition_type="none", # Переходы пока не передаем
            # transition_duration_secs=0.3
        )
        single_montage_end_time = time.time()

        if success:
            processed_montages +=1
            print(f"Видеомонтаж #{i+1} создан за {single_montage_end_time - single_montage_start_time:.2f} сек.")
        else:
            print(f"Ошибка при создании видеомонтажа #{i+1}.")

    total_end_time = time.time()
    print(f"\n--- Завершено ---")
    print(f"Всего успешно создано видеомонтажей: {processed_montages} из {args.num_montages} запланированных.")
    print(f"Общее время выполнения: {total_end_time - total_start_time:.2f} секунд.")