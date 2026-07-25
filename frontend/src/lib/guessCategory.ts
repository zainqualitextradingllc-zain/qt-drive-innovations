/** Coarse bucket for PostHog only — never send raw symptom text. */
export function guessCategory(text: string): string {
  const t = text.toLowerCase().normalize("NFKC");

  const rules: Array<{ cat: string; keys: string[] }> = [
    {
      cat: "brakes",
      keys: [
        "brake",
        "brakes",
        "grinding",
        "squeal",
        "squeaking",
        "abs",
        "ブレーキ",
        "効かない",
        "キーキー",
        "ジージー",
        "鳴る",
      ],
    },
    {
      cat: "engine",
      keys: [
        "engine",
        "misfire",
        "stall",
        "overheat",
        "check engine",
        "cel",
        "エンジン",
        "エンスト",
        "オーバーヒート",
        "警告灯",
      ],
    },
    {
      cat: "transmission",
      keys: [
        "transmission",
        "gear",
        "clutch",
        "cvt",
        "shift",
        "ミッション",
        "変速",
        "クラッチ",
        "ギア",
      ],
    },
    {
      cat: "electrical",
      keys: [
        "battery",
        "alternator",
        "won't start",
        "wont start",
        "dead",
        "electrical",
        "バッテリー",
        "オルタネーター",
        "始動",
        "電気",
      ],
    },
    {
      cat: "suspension_steering",
      keys: [
        "steering",
        "alignment",
        "shock",
        "strut",
        "vibration",
        "pulls",
        "ステアリング",
        "ハンドル",
        "サスペンション",
        "振動",
        "片寄り",
      ],
    },
    {
      cat: "cooling_ac",
      keys: [
        "ac",
        "a/c",
        "air conditioning",
        "heater",
        "coolant",
        "radiator",
        "エアコン",
        "クーラー",
        "ヒーター",
        "冷却",
        "ラジエーター",
      ],
    },
    {
      cat: "exhaust_emissions",
      keys: [
        "exhaust",
        "smoke",
        "catalytic",
        "dpf",
        "emissions",
        "排気",
        "煙",
        "白煙",
        "黒煙",
      ],
    },
    {
      cat: "tires_wheels",
      keys: ["tire", "tyre", "wheel", "puncture", "flat", "タイヤ", "ホイール", "パンク"],
    },
  ];

  for (const { cat, keys } of rules) {
    if (keys.some((k) => t.includes(k.toLowerCase()))) return cat;
  }
  return "other";
}
