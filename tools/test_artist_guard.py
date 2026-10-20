#!/usr/bin/env python3
"""藝名保護條目的回歸測試。

驗證三件事：
  1. 受保護的藝名：繁體輸入不被改壞、簡體輸入轉成正確繁體
  2. 非保護的藝名：轉換結果不受影響（不被連帶誤傷）
  3. 既有轉換行為：關鍵回歸案例的輸出與修改前一致

用法：
    python3 tools/test_artist_guard.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opencc import OpenCC  # noqa: E402

from tools.gen_artist_guard import ARTISTS  # noqa: E402

# 受保護藝名：(繁體正名, 簡體形)
# 繁體正名必須是台灣/華語藝人的通行寫法
GUARDED: list[tuple[str, str]] = [
    ('于文文', '于文文'),
    ('于果', '于果'),
    ('于朦朧', '于朦胧'),
    ('于恆', '于恒'),
    ('于謙', '于谦'),
    ('范曉萱', '范晓萱'),
    ('范瑋琪', '范玮琪'),
    ('范丞丞', '范丞丞'),
    ('范世錡', '范世锜'),
    ('范少勳', '范少勋'),
    ('范鴻軒', '范鸿轩'),
    ('范志博', '范志博'),
    ('范薇', '范薇'),
    ('范滄東', '范沧东'),
    ('范逸臣', '范逸臣'),
    ('游鴻明', '游鸿明'),
    ('游安迪', '游安迪'),
    ('游智淵', '游智渊'),
    ('游乃翔', '游乃翔'),
    ('游昌鎮', '游昌镇'),
    ('游耀忠', '游耀忠'),
    ('朴鯊', '朴鲨'),
    ('朴有天', '朴有天'),
    ('朴信惠', '朴信惠'),
    ('朴寶英', '朴宝英'),
    ('朴政珉', '朴政珉'),
    ('朴有鎮', '朴有镇'),
    ('朴俊亨', '朴俊亨'),
    ('朴海養', '朴海养'),
    ('朴寶劍', '朴宝剑'),
    ('朴燦星', '朴灿星'),
    ('朴沙星', '朴沙星'),
    ('朴樹', '朴树'),
    ('岳雲鵬', '岳云鹏'),
    ('岳飛', '岳飞'),
    ('岳麗娜', '岳丽娜'),
    ('回音哥', '回音哥'),
    ('干露', '干露'),
    ('鍾欣潼', '钟欣潼'),
    ('钟不悔', '钟不悔'),
    ('汪蘇瀧', '汪苏泷'),
    ('馬郁', '马郁'),
    ('張震嶽', '张震岳'),
]

# 非保護藝名：常見華語歌手，轉換結果必須正確（不被連帶誤傷）
UNTOUCHED: list[tuple[str, str]] = [
    ('周杰倫', '周杰伦'),
    ('蔡依林', '蔡依林'),
    ('蕭敬騰', '萧敬腾'),
    ('林俊傑', '林俊杰'),
    ('張惠妹', '张惠妹'),
    ('梁靜茹', '梁静茹'),
    ('孫楠', '孙楠'),
    ('陳奕迅', '陈奕迅'),
    ('五月天', '五月天'),
    ('王力宏', '王力宏'),
    ('張靚穎', '张靓颖'),
    ('鄧紫棋', '邓紫棋'),
    ('單依純', '单依纯'),
    ('胡夏', '胡夏'),
    ('霍尊', '霍尊'),
    ('李榮浩', '李荣浩'),
    ('薛之謙', '薛之谦'),
    ('陳粒', '陈粒'),
    ('顏人中', '颜人中'),
    ('陳楚生', '陈楚生'),
    ('徐佳瑩', '徐佳莹'),
    ('李聖傑', '李圣杰'),
    ('蔡健雅', '蔡健雅'),
    ('張韶涵', '张韶涵'),
    ('莫文蔚', '莫文蔚'),
    ('潘越雲', '潘越云'),
    ('黃韻玲', '黄韵玲'),
    ('江蕙', '江蕙'),
    ('伍佰', '伍佰'),
    ('羅大佑', '罗大佑'),
    ('李宗盛', '李宗盛'),
    ('陶喆', '陶喆'),
    ('方大同', '方大同'),
    ('張學友', '张学友'),
    ('黎明', '黎明'),
    ('劉德華', '刘德华'),
    ('王傑', '王杰'),
    ('謝霆鋒', '谢霆锋'),
    ('蔡卓妍', '蔡卓妍'),
    ('容祖兒', '容祖儿'),
    ('楊千嬅', '杨千嬅'),
    ('鄭秀文', '郑秀文'),
    ('陳慧琳', '陈慧琳'),
    ('陳慧嫻', '陈慧娴'),
    ('梁詠琪', '梁咏琪'),
    ('李聖傑', '李圣杰'),
    ('胡彥斌', '胡彦斌'),
    ('蘇見信', '苏见信'),
    ('朴樹', '朴树'),
]

# 既有轉換行為的回歸案例（期望值＝修改前行為）
REGRESSION: list[tuple[str, str]] = [
    ('医生发出，断发纹身', '醫生發出，斷髮紋身'),
    ('校长发起，队长成长', '校長發起，隊長成長'),
    ('但是只有她，明白发生了', '但是只有她，明白發生了'),
    ('一直发抖，直发呆', '一直發抖，直發呆'),
    ('这是只猫，是只母', '這是只貓，是隻母'),
    ('的士兵，通讯的士兵', '的士兵，通訊的士兵'),
    ('台湾的台式机', '台灣的桌上型電腦'),
    ('对象，循环，菜单', '對象，循環，菜單'),
    ('重装备，重装甲', '重裝備，重裝甲'),
    ('姜蓉，姜丝，蒜蓉', '姜蓉，薑絲，蒜蓉'),
    ('五岳，岳父，岳飞，岳不群', '五嶽，岳父，岳飛，岳不群'),
    ('游泳，上游，游击，游离', '游泳，上游，游擊，游離'),
    ('后车斗，后备箱', '後車斗，後備箱'),
    ('面包，场面，几片面包', '麵包，場面，幾片麵包'),
    ('网络，打开，高级', '網路，開啟，高階'),
    ('干部，干活，干燥', '幹部，幹活，乾燥'),
    ('面条，面包', '麵條，麵包'),
    ('台湾，臺灣', '台灣，臺灣'),
    ('一只鸟', '一隻鳥'),
    ('头发，长发', '頭髮，長髮'),
    ('沈从文，沈括', '沈從文，沈括'),
    ('茅台，台酒', '茅台，台酒'),
]


def main() -> int:
    """執行回歸測試，回傳失敗數作為結束碼。"""
    cc = OpenCC('s2twp-custom-mpdp')
    failures: list[str] = []

    print('=== 1. 受保護藝名（繁體輸入不應被改壞）===')
    for trad, _ in GUARDED:
        out = cc.convert(trad)
        if out != trad:
            failures.append(f'繁體被改壞：{trad} → {out}')
            print(f'  BAD {trad} → {out}')
        else:
            print(f'  OK  {trad}')

    print()
    print('=== 2. 受保護藝名（簡體輸入應轉成正確繁體）===')
    for trad, simp in GUARDED:
        out = cc.convert(simp)
        if out != trad:
            failures.append(f'簡體轉換錯誤：{simp} → {out}（期望 {trad}）')
            print(f'  BAD {simp} → {out}（期望 {trad}）')
        else:
            print(f'  OK  {simp} → {out}')

    print()
    print('=== 3. 非保護藝名（不應被連帶誤傷）===')
    for trad, simp in UNTOUCHED:
        out = cc.convert(simp)
        if out != trad:
            failures.append(f'藝名被誤傷：{simp} → {out}（期望 {trad}）')
            print(f'  BAD {simp} → {out}（期望 {trad}）')
        else:
            print(f'  OK  {simp} → {out}')

    print()
    print('=== 4. 既有轉換行為回歸 ===')
    for src, want in REGRESSION:
        out = cc.convert(src)
        if out != want:
            failures.append(f'回歸失敗：{src} → {out}（期望 {want}）')
            print(f'  BAD {src} → {out}（期望 {want}）')
        else:
            print(f'  OK  {src} → {out}')

    print()
    print('=== 5. 冪等性（轉換兩次結果相同）===')
    for trad, _ in GUARDED:
        once = cc.convert(trad)
        twice = cc.convert(once)
        if once != twice:
            failures.append(f'非冪等：{trad} → {once} → {twice}')
            print(f'  BAD {trad} → {once} → {twice}')
    if not any('非冪等' in f for f in failures):
        print(f'  OK  {len(GUARDED)} 個受保護藝名全部冪等')

    print()
    print('=== 6. 副作用檢測（自我映射條目不得拖累常見詞組）===')
    # 自我映射條目（「于震→于震」型）會與常見詞組競爭：
    # 若「于震」在 mpdp 分割中勝出，「过于震驚」就會被誤轉成「過于震驚」。
    # 這是 2026-10 實測踩到的坑（15 個 2 字條目造成 315 個副作用）。
    SIDE_EFFECTS: list[tuple[str, str]] = [
        ('过于震惊', '過於震驚'),
        ('过于他人', '過於他人'),
        ('过于他', '過於他'),
        ('后于人', '後於人'),
        ('有人于', '有人於'),
        ('过于', '過於'),
        ('朴素', '樸素'),
        ('干活', '幹活'),
        ('干燥', '乾燥'),
        ('回答', '回答'),
        ('回来', '回來'),
        ('范围', '範圍'),
        ('模范', '模範'),
        ('马上', '馬上'),
        ('回音', '迴音'),
    ]
    for src, want in SIDE_EFFECTS:
        out = cc.convert(src)
        if out != want:
            failures.append(f'副作用：{src} → {out}（期望 {want}）')
            print(f'  BAD {src} → {out}（期望 {want}）')
        else:
            print(f'  OK  {src} → {out}')

    # 藝名保護條目不得為 2 字自我映射（與 upstream 人名條目皆 3 字以上的設計一致）。
    # 唯一例外：音樂庫實際存在的 2 字名（于果、朴鯊、馬郁…），
    # 經逐一驗證對常見詞組無影響（見下方 SIDE_EFFECTS）。
    # ⚠️ 高危首字是「于」（于→於）：2 字的「于X」會與「过于震驚」類詞組競爭。
    #    已移除的 15 個 2 字「于X」條目共造成 315 個副作用（實測）。
    ALLOWED_TWO_CHAR = {'于果', '范薇', '朴鯊', '朴樹', '岳飛', '干露', '馬郁', '于恆', '于謙'}
    two_char = {t for t, _ in ARTISTS if len(t) == 2}
    bad_two = two_char - ALLOWED_TWO_CHAR
    if bad_two:
        failures.append(f'含未核准的 2 字自我映射條目（高副作用風險）：{sorted(bad_two)}')
        print(f'  BAD 2 字條目：{sorted(bad_two)}')
    else:
        print(f'  OK  2 字條目僅含已逐一驗證者：{sorted(two_char)}')
    # 2 字「于X」有與「过于X」詞組衝突的風險（實測：「于震」曾使
    # 「過于震驚」誤轉，因「震驚」高頻把 DP 拉向「于|震驚」）。
    # 但並非所有 2 字「于X」都有問題——關鍵在 mpdp 詞表的競爭強度：
    # 「过于」(freq 1775) 遠高於「于果」「于恒」「于谦」(freq 100)，
    # 故後者不致搶走切分。實際風險必須用**真實詞組**逐一實測，
    # 不可用構造詞（如「过于果震驚」不是任何中文詞，會誤判）。
    risky_yu = {t for t in two_char if t.startswith('于')}
    REAL_PROBES = ['过于', '过于自信', '过于担心', '过于害怕', '过于重视',
                   '由于', '由于此', '果不其然', '谦虚', '谦逊', '恒心', '恒久']
    for probe in REAL_PROBES:
        out = cc.convert(probe)
        if '于' in out:
            failures.append(f'2 字「于X」條目造成副作用：{probe} → {out}')
            print(f'  BAD {probe!r} → {out!r}（殘留「于」）')
        else:
            print(f'  OK  {probe!r} → {out!r}')

    print()
    print('=== 7. overlay 與產生器一致性 ===')
    gen_keys = {k for k, _ in ARTISTS} | {v for _, v in ARTISTS}
    guard_keys = {k for k, _ in GUARDED} | {v for _, v in GUARDED}
    missing = gen_keys - guard_keys
    if missing:
        failures.append(f'產生器與測試不一致，缺：{sorted(missing)}')
        print(f'  BAD 缺 {sorted(missing)}')
    else:
        print(f'  OK  產生器 {len(ARTISTS)} 筆與測試 {len(GUARDED)} 筆一致')

    print()
    print('=' * 60)
    if failures:
        print(f'失敗 {len(failures)} 項：')
        for f in failures:
            print(f'  - {f}')
        return 1
    print('全部通過')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
