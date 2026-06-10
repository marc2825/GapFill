# GapFill: No Pixel Left Behind: Filling Gaps in Anime Colorization

[![CHI '26](https://img.shields.io/badge/CHI_'26-Accepted-green)](https://doi.org/10.1145/3772318.3790968)
[![WISS '25](https://img.shields.io/badge/WISS_'25-Presented-orange)](https://www.wiss.org/WISS2025Proceedings/data/demo/2-C15.pdf)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[![Explore GapFill](https://img.shields.io/badge/Explore_GapFill-Project_Website-2ea44f?style=for-the-badge&logo=github)](https://marc2825.github.io/GapFill/)

![GapFill teaser figure](docs/images/Teaser.png)


**[WIP] Source code for the web application and the trained model will be released soon [WIP]**


**GapFill** is an interactive tool for helping professional anime colorists
detect and fill small unpainted enclosed regions, or **"gaps" (塗り残し)** that are often
left behind during digital manual colorization.

The system automatically detects gaps, highlights them, and suggests fill
colors using a domain-specific deep-learning method that learns
correspondences between image regions. GapFill also provides pop-up
magnification, manual color correction, and sweep-to-apply interactions,
reducing the repetitive work of finding gaps, zooming in, and selecting colors.


## Quick Start

This repository contains two components. Refer to the README for each component
for installation, data preparation, and usage instructions.

| Component | Description | Setup and usage |
|---|---|---|
| Web application (`web/`) | Interactive GapFill interface for detecting, inspecting, and filling gaps | [Web application README](web/README.md) |
| Machine-learning pipeline (`ml/`) | Data preprocessing, model training, evaluation, and visualization | [ML pipeline README](ml/README.md) |

## Citation

If you use GapFill in your research, please cite our paper:

```bibtex
@inproceedings{kono2026gapfill,
  author    = {Masahiro Kono and Akinobu Maejima and Yuki Koyama and
               Yotam Sechayk and Takeo Igarashi},
  title     = {No Pixel Left Behind: Filling Gaps in Anime Colorization},
  booktitle = {Proceedings of the 2026 CHI Conference on Human Factors in
               Computing Systems},
  year      = {2026},
  doi       = {10.1145/3772318.3790968}
}
```

Machine-readable citation metadata is available in [CITATION.cff](CITATION.cff).

## License

This project is released under the [MIT License](LICENSE).

## Updates

- **June 10, 2026:** Source code (refactored) for the GapFill model is available.
- **March 10, 2026:** The project website, paper, and demo web application are
  available.
- Source code for the web application and the trained model will be released
  soon.
