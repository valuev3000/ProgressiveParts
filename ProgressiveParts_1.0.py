#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
from collections import defaultdict

# ================= НАСТРОЙКИ =================
# Диапазоны давления и температуры
PRESSURE_MIN = 4000      # кПа для самого раннего узла
PRESSURE_MAX = 15500     # кПа для самого позднего узла
TEMP_MIN = 2000          # K для самого раннего узла
TEMP_MAX = 5500          # K для самого позднего узла

# Списки технологических узлов для каждой категории (от раннего к позднему)
# Длина списка определяет количество уровней для данной категории.
CATEGORY_NODES = {
    "probe": [
        "start",
        "basicScience",
        "miniaturization",
        "precisionEngineering",
        "unmannedTech",
        "advUnmanned",
        "largeUnmanned"
    ],
    "command": [
        "survivability",
        "enhancedSurvivability",
        "simpleCommandModules",
        "commandModules",
        "heavyCommandModules",
        "specializedCommandModules",
        "heavyCommandCenters"
    ],
    "wheel": [
        "fieldScience",
        "robotics",
        "advActuators",
        "experimentalActuators",
        "advancedMotors",
        "experimentalMotors",
        "mechatronics"
    ],
    "heatshield": [
        "survivability",
        "stability",
        "aviation",
        "aerodynamicSystems",
        "advAerodynamics",
        "heavyAerodynamics",
        "advancedAerodynamics"
    ],
    "rtg": [
        "electrics",
        "advElectrics",
        "largeElectrics",
        "specializedElectrics",
        "experimentalElectrics",
        "highTechElectricalSystems",
        "highPowerElectricalSystems"
    ],
    "battery": [
        "electrics",
        "advElectrics",
        "largeElectrics",
        "specializedElectrics",
        "experimentalElectrics",
        "highTechElectricalSystems",
        "highPowerElectricalSystems"
    ],
    "light": [
        "electrics",
        "advElectrics",
        "largeElectrics",
        "specializedElectrics",
        "experimentalElectrics",
        "highTechElectricalSystems",
        "highPowerElectricalSystems"
    ],
    "parachute": [
        "survivability",
        "stability",
        "aviation",
        "aerodynamicSystems",
        "advAerodynamics",
        "heavyAerodynamics",
        "advancedAerodynamics"
    ],
}

# Ключевые слова для определения типа детали
KEYWORDS = {
    "probe": ["probeCore", "probe", "core", "computer"],
    "command": ["command", "capsule", "pod", "crew", "cockpit"],
    "wheel": ["wheel", "rover", "track", "landing gear", "wheelMed", "wheelSmall", "wheelLarge"],
    "heatshield": ["heatshield", "ablator", "thermal protection"],
    "rtg": ["rtg", "radioisotope", "nuclear battery"],
    "battery": ["battery", "Battery"],
    "light": ["light", "lamp", "led", "floodlight", "spotlight"],
    "parachute": ["parachute", "chute", "drogue", "parachuteRadial"],
}
ALL_KEYWORDS = [kw for sublist in KEYWORDS.values() for kw in sublist]

# Множители характеристик (индекс 0 соответствует самому раннему уровню, индекс -1 – самому позднему)
# Если нужна интерполяция множителей, можно доработать, но пока оставим жёстко заданными.
LEVEL_MODIFIERS = {
    "mass": [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2],
    "battery_capacity": [1.0, 1.3, 1.7, 2.2, 2.8, 3.5, 4.3],
    "antenna_range": [1.0, 1.5, 2.2, 3.2, 4.5, 6.0, 8.0],
    "actuator_speed": [1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 3.6],
    "actuator_range": [1.0, 1.2, 1.4, 1.7, 2.0, 2.4, 2.8],
    "light_power": [1.0, 1.5, 2.2, 3.2, 4.5, 6.0, 8.0],
    "light_range": [1.0, 1.3, 1.7, 2.2, 2.8, 3.5, 4.3],
    "parachute_drag": [1.0, 1.3, 1.7, 2.2, 2.8, 3.5, 4.3],
}

PART_TYPE_MODS = {
    "battery": ["battery_capacity"],
    "antenna": ["antenna_range"],
    "comm": ["antenna_range"],
    "actuator": ["actuator_speed", "actuator_range"],
    "light": ["light_power", "light_range"],
    "parachute": ["parachute_drag"]
}
DEFAULT_MODS = ["mass"]

OUTPUT_CFG = "TieredPartsByCategory.cfg"

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def linear_interpolate(value_min, value_max, index, total_steps):
    """Линейная интерполяция: index от 0 до total_steps-1, возвращает целое число"""
    if total_steps <= 1:
        return value_min
    fraction = index / (total_steps - 1)
    return int(round(value_min + (value_max - value_min) * fraction))

def get_category_modifiers(category):
    """Возвращает список модификаторов для данной категории (по умолчанию ['mass'])"""
    if category in PART_TYPE_MODS:
        return PART_TYPE_MODS[category]
    return DEFAULT_MODS

# ===== ПОИСК ДЕТАЛЕЙ =====
def find_part_files(gamedata_path):
    part_files = []
    for root, _, files in os.walk(gamedata_path):
        for f in files:
            if f.endswith(".cfg"):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding="utf-8") as file:
                        if "PART" in file.read():
                            part_files.append(path)
                except:
                    pass
    return part_files

def get_part_category(name):
    name_lower = name.lower()
    for cat, keywords in KEYWORDS.items():
        if any(kw.lower() in name_lower for kw in keywords):
            return cat
    return None

def extract_part_names(files):
    parts = set()
    for f in files:
        try:
            with open(f, encoding="utf-8") as file:
                txt = file.read()
            m = re.search(r'name\s*=\s*(\S+)', txt)
            if m:
                name = m.group(1)
                if any(kw.lower() in name.lower() for kw in ALL_KEYWORDS):
                    parts.add(name)
        except:
            pass
    return sorted(parts)

# ===== ГЕНЕРАЦИЯ ПАТЧА =====
def generate_patch(part, category, tier_index, total_tiers, tech_node):
    """
    tier_index: 0-based (0 = самый ранний уровень)
    total_tiers: общее количество уровней для этой категории
    """
    pressure = linear_interpolate(PRESSURE_MIN, PRESSURE_MAX, tier_index, total_tiers)
    temp = linear_interpolate(TEMP_MIN, TEMP_MAX, tier_index, total_tiers)
    tier_num = tier_index + 1

    mods = get_category_modifiers(category)
    mod_lines = []
    if "mass" in mods:
        mult = LEVEL_MODIFIERS["mass"][tier_index]
        mod_lines.append(f"    @mass *= {mult}")
    if "battery_capacity" in mods:
        mult = LEVEL_MODIFIERS["battery_capacity"][tier_index]
        mod_lines += [
            "    @RESOURCE[ElectricCharge]",
            "    {",
            f"        @amount *= {mult}",
            f"        @maxAmount *= {mult}",
            "    }"
        ]
    if "antenna_range" in mods:
        mult = LEVEL_MODIFIERS["antenna_range"][tier_index]
        mod_lines += [
            "    @MODULE[ModuleDataTransmitter]",
            "    {",
            f"        @antennaPower *= {mult}",
            "    }"
        ]
    if "actuator_speed" in mods:
        speed_mult = LEVEL_MODIFIERS["actuator_speed"][tier_index]
        mod_lines += [
            "    @MODULE[ModuleGimbal]",
            "    {",
            f"        @gimbalResponseSpeed *= {speed_mult}",
            "    }",
            "    @MODULE[ModuleRoboticServoHinge],MODULE[ModuleRoboticServoPiston]",
            "    {",
            f"        @maxSpeed *= {speed_mult}",
            "    }"
        ]
    if "actuator_range" in mods:
        range_mult = LEVEL_MODIFIERS["actuator_range"][tier_index]
        mod_lines += [
            "    @MODULE[ModuleGimbal]",
            "    {",
            f"        @gimbalRange *= {range_mult}",
            "    }",
            "    @MODULE[ModuleRoboticServoHinge],MODULE[ModuleRoboticServoPiston]",
            "    {",
            f"        @maxRange *= {range_mult}",
            "    }"
        ]
    if "light_power" in mods:
        power_mult = LEVEL_MODIFIERS["light_power"][tier_index]
        mod_lines += [
            "    @MODULE[ModuleLight]",
            "    {",
            f"        @lumens *= {power_mult}",
            "    }"
        ]
    if "light_range" in mods:
        range_mult = LEVEL_MODIFIERS["light_range"][tier_index]
        mod_lines += [
            "    @MODULE[ModuleLight]",
            "    {",
            f"        @lightRange *= {range_mult}",
            "    }"
        ]
    if "parachute_drag" in mods:
        drag_mult = LEVEL_MODIFIERS["parachute_drag"][tier_index]
        mod_lines += [
            "    @MODULE[ModuleParachute]",
            "    {",
            f"        @semiDeployedDrag *= {drag_mult}",
            f"        @fullyDeployedDrag *= {drag_mult}",
            "    }",
            "    @MODULE[ModuleParachute]",
            "    {",
            f"        @deployTime /= {drag_mult}",
            "    }"
        ]

    mod_text = "\n".join(mod_lines) if mod_lines else ""

    cleanup = """
    !MODULE[Reliability] {}
    !MODULE[PressureLimit] {}
    !MODULE[TemperatureLimit] {}
"""
    extra_fields = f"""
    %maxPressure = {pressure}
    %maxTemp = {temp}
"""

    return f"""
// Tier {tier_num} for {part} (category: {category}) -> {tech_node}
+PART[{part}]:NEEDS[Kerbalism]
{{
    @name = {part}_L{tier_num}
    @title = {part} L{tier_num}
    @description = Tier {tier_num}\\nPressure: {pressure} kPa\\nTemp: {temp}K

{mod_text}
{cleanup}
{extra_fields}
    %MODULE[Reliability]
    {{
        %type = Kerbalism
        %pressure = {pressure}
        %temperature = {temp}
    }}

    @TechRequired = {tech_node}
}}
"""

# ===== MAIN =====
def main():
    print("=== Генератор уровневых деталей с автоматическим расчётом давления/температуры по прогрессии узлов ===")
    print(f"Диапазон: давление {PRESSURE_MIN}-{PRESSURE_MAX} кПа, температура {TEMP_MIN}-{TEMP_MAX} K")

    # Выбор GameData
    if len(sys.argv) > 1:
        gamedata_path = sys.argv[1]
        if not os.path.exists(gamedata_path):
            print(f"❌ Путь не существует: {gamedata_path}")
            return
    else:
        print("Введите путь к папке GameData (пример: D:\\Games\\KSP\\GameData)")
        while True:
            path = input("> ").strip().strip('"')
            if os.path.exists(path) and path.lower().endswith("gamedata"):
                gamedata_path = path
                break
            print("❌ Неверный путь, попробуй ещё раз")

    print("Используется GameData:", gamedata_path)

    # Поиск деталей
    part_files = find_part_files(gamedata_path)
    parts = extract_part_names(part_files)
    if not parts:
        print("❌ Детали не найдены")
        return

    # Группировка по категориям
    categorized = defaultdict(list)
    for p in parts:
        cat = get_part_category(p)
        if cat and cat in CATEGORY_NODES:
            categorized[cat].append(p)
        else:
            print(f"⚠️ Деталь {p} не попала ни в одну категорию (или категория не поддерживается) — пропущена")

    if not categorized:
        print("❌ Нет деталей подходящих категорий")
        return

    print("Найдено деталей по категориям:")
    for cat, lst in categorized.items():
        print(f"  {cat}: {len(lst)}")

    # Генерация выходного файла
    out_path = os.path.join(os.getcwd(), OUTPUT_CFG)
    with open(out_path, "w", encoding="utf-8") as out:
        for cat, part_list in categorized.items():
            nodes = CATEGORY_NODES[cat]
            total_tiers = len(nodes)
            print(f"\nГенерация для категории {cat} ({total_tiers} уровней):")
            for tier_idx, tech_node in enumerate(nodes):
                pressure = linear_interpolate(PRESSURE_MIN, PRESSURE_MAX, tier_idx, total_tiers)
                temp = linear_interpolate(TEMP_MIN, TEMP_MAX, tier_idx, total_tiers)
                print(f"  Tier {tier_idx+1}: {tech_node} -> {pressure} kPa, {temp} K")
                for part in part_list:
                    out.write(generate_patch(part, cat, tier_idx, total_tiers, tech_node))

    print(f"\n✅ Готово! Создан файл: {out_path}")
    print("Скопируйте его в любую подпапку GameData.")
    print("Убедитесь, что установлен Kerbalism.")
    print("Теперь давление и температура для каждой копии детали зависят от положения узла в прогрессии категории.")

if __name__ == "__main__":
    main()