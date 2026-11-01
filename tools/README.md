# tools

构建 / 验证关卡数据用的脚本。游戏本身是自包含的 `index.html`，运行时不依赖这里。

Scripts used to build / verify the level data. The game itself is a
self-contained `index.html` and does **not** need anything here at runtime.

## 关卡数据来源 · Where the levels come from

27 个动物 / 物件轮廓（猫、狗、天鹅、鱼、恐龙……）来自 **KiloGram** 数据集：

The 27 animal / object silhouettes come from the **KiloGram** dataset:

- https://github.com/lil-lab/kilogram
- Y. Bitton, N. Yoran, et al. *KiloGram: A Dataset of Human-Played Tangram
  Puzzles.* (EMNLP 2022)

该数据集里的每个 SVG 都以多边形（id 1–7）的形式给出七块拼板的位置，
因此可以精确还原轮廓与解法。这些图形是从下面这本书的扫描件数字化的：

Each SVG in that dataset lists the seven tangram pieces as polygons
(ids 1–7), so the silhouette *and* its solution can be recovered exactly.
The figures were digitised from scans of:

> J. Slocum. 2003. *The Tangram Book: The Story of the Chinese Puzzle with
> over 2000 Puzzles to Solve.* Sterling Publishing, New York.

> **License / 许可**: KiloGram 的代码采用 MIT 许可；但其中的 Tangram 图像
> （含 `tangrams-svg/`）仅根据普林斯顿图书馆的声明，**供教育与研究用途**。
> 本项目只提取了多边形的顶点坐标，用于非商业的教育 / 个人用途，并在此注明出处。
>
> KiloGram's *code* is MIT-licensed, but its tangram **images** are digitised
> from the book above and are made available for **educational and research
> use** per the Princeton Library notice. This project only extracts the
> polygons' vertex coordinates for non-commercial, educational/personal use,
> and credits the source here.

其余 3 个经典关卡（Square / Triangle / Rectangle）由 `solve.py` 现场求解得到。

The other 3 classic levels (Square / Triangle / Rectangle) are solved from
scratch by `solve.py`.

## 用法 · Usage

```sh
cd tools
python3 build_puzzles.py            # 下载 SVG、生成 puzzles.json
python3 build_puzzles.py --inject   # 顺便把数据写回 ../index.html
python3 make_preview.py             # 重新生成 ../preview.svg
```

`build_puzzles.py` 会：

1. 把所选图形从 KiloGram 仓库下载到 `kg_svg/`（已忽略，不提交）；
2. 解析每个 SVG 的 7 个多边形，按面积 / 形状判定它是哪一块拼板，
   并记录其朝向（45° 的整数倍）与是否镜像；
3. 归一化到「标准七巧板单位」（小三角形直角边 = 1），把图形包围盒移到原点；
4. 用 `solve.py` 求解三个经典关卡；
5. 写出 `puzzles.json`，并可选择写回 `index.html` 内嵌的
   `<script id="puzzles-data">`。

### 几何约定 · Geometry

标准拼板（小三角形直角边 = 1）：

| 名称 | 类型 | 顶点 |
| --- | --- | --- |
| 小三角形 ×2 | `S` | `(0,0) (1,0) (0,1)` |
| 中三角形 ×1 | `M` | `(0,0) (2,0) (1,1)` |
| 大三角形 ×2 | `L` | `(0,0) (2,0) (0,2)` |
| 正方形 ×1   | `Q` | `(0,0) (1,0) (1,1) (0,1)` |
| 平行四边形 ×1 | `P` | `(0,0) (1,0) (2,1) (1,1)` |

每块可旋转 45° 的整数倍（8 个朝向）；平行四边形额外可镜像。
