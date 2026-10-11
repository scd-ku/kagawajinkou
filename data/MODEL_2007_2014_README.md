# 2007–2014年・香川県内市町間移動：坂道推計の仕様

**重要：この期間の市町間OD値は観測値ではなくモデル推計値です。** 2015–2025年の観測ODと区別してください。

## 観測された数値
香川県「香川県人口移動調査報告（年報）」第4表の17市町別「県内からの転入人数」「県内への転出人数」（いずれも実数）を年別に採録しています。
- [市町別の出入実数 CSV](kagawa_2007_2014_marginals_official.csv)
- [市町間の推計OD CSV](kagawa_od_2007_2014_modeled.csv)
- 2007: https://opendata.pref.kagawa.lg.jp/dataset/834/resource/14669/content.html
- 2008: https://opendata.pref.kagawa.lg.jp/dataset/835/resource/14686/content.html
- 2009: https://opendata.pref.kagawa.lg.jp/dataset/836/resource/14703/content.html
- 2010: https://opendata.pref.kagawa.lg.jp/dataset/839/resource/14751/content.html
- 2011: https://opendata.pref.kagawa.lg.jp/dataset/838/resource/14735/content.html
- 2012: https://opendata.pref.kagawa.lg.jp/dataset/840/resource/14758/content.html
- 2013: https://opendata.pref.kagawa.lg.jp/dataset/217/resource/1770/content.html
- 2014: https://opendata.pref.kagawa.lg.jp/dataset/218/resource/1786/content.html

## 推計方法
1. 自市町への転入をゼロとし、残る16市町への重みを2次元の地図座標間距離 `d` で `w = exp(-d/135) + 0.025` とする（近接性を仮定する重力型事前重み）。
2. 各年の市町別「県内への転出人数」を発地の行和、「県内からの転入人数」を着地の列和として反復比例調整（IPF）を1,500回行う。
3. 県全体の入出計には年間6〜69人程度の差があるため、着地の総和のみ `県内転出総数 / 県内転入総数` で一様に調整する。その結果、出地の実測転出合計は一致し、着地のモデル転入合計は公式値からわずかに異なる。**移動元と移動先の組み合わせは一切実測されていない。**
4. 男女内訳も個別ODとしての実測ではなく、e-Statの転入先別・県内転入の男女構成比を各着地に適用して割り当てた推計値である。

この推計は教育・可視化上の仮定です。坂道の方向・太さから**特定市町間の実移動数を推測しないでください**。科学的推論や政策評価には別途実測ODの取得が必要です。

> 編集上の注意：坂道UIは2007〜2014年を「推計」、2015〜2025年を「実測」と明示し、2014→2015年の中間フレームは両者を補間していることを表示します。
