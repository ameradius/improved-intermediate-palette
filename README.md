# Improved Intermediate Palette 

![4 pool ball drawn with the improved intermediate palette](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/ImprovedIntermediatePalette.png)
4 pool ball I drew myself with the improved intermediate palette.

A Krita plugin fork of [Tayete's Intermediate Palette Plugin](https://krita-artists.org/t/intermediate-palette-for-krita-docker/) from the Krita Forum designed for creating intermediate palettes by putting anchor swatches with lots of additions and interface changes. Notably:
- **Solvers & mixers.** You have the ability to change **how the colors are mixed** and **how the colors affect the palette** separately. Consult this [README](./improved_intermediate_palette/README.md) to see how the detailed math works. In addition to that, the four anchors on the corners now isn't a hard requirement; you can delete them as you like.
  ![Solver Mixer](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/SolverMixer.png)
- **Palette chooser.** Save your palettes and load them in a single directory with each palette showing essential info such as its thumbnail and metadata, creating an easier workflow to organize palettes, to paint or any other uses.
  ![Palette Chooser](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/PaletteChooser.png)
- **Color history.** You can look at your color history up to 20 colors.
  ![Color History](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/ColorHistory.png)
- **Improvement and additions to anchors.** They are now way more readable (a little right triangle on top left with contrasting color) and you can check them in the Anchors dropdown. Right-clicking is feels finicky on a drawing tablet, so I added a Ctrl + Click/Long press shortcuts for the grids.
  ![Anchors List](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/Screenshot_20260919_193620.png)
- **Color sampling**. Currently, it's just your default operating system color selector. Haven't got the time to properly add native Krita's color picking so that's in the future.
- UI/UX changes and additions such as
    - cursor hovering over the grid highlights them,
    - moved plugin controls info to a hoverable (?) icon,
    - matching the palette's canvas background to the theme,
      ![Theme 1](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/GrayIIP.png) ![Theme 2](https://file.garden/apes3Jfn0maeAVMw/ImprovedIntermediatePlugin/WhiteIIP.png)
    - lastly picked color grid highlight,
    - etc.

To install this, click the green **<> Code** button on the header and click **Download ZIP**. Navigate to **Tools > Scripts > Import Python Plugin From File** in Krita and select the downloaded ZIP. Restart Krita.


## Credits & Acknowledgments

This plugin is based on an initial concept shared by [**Tayete**](https://krita-artists.org/u/tayete) at [Intermediate Palette Plugin Krita Forum Post](https://krita-artists.org/t/intermediate-palette-for-krita-docker/), which were distributed via Google Drive. I can't officially fork it so I had to point out where credits were due! I'm thankful for the original developer. I have a lot of desires in mind so I had to take it into my own hand as a mathematician and a developer.

The codebase has since been significantly refactored and expanded with new solvers and color mixers, a palette chooser, and lots of QOL additions and UX improvements. I will welcome any pull requests (preferably solvers or mixers), suggestions or any bug reports. 

## License

- **License:** This project is licensed under the [GNU General Public License v3.0 or later](LICENSE) (`GPL-3.0-or-later`).
- **Original Concept:** Based on an initial script and idea originally shared by [**Tayete**](https://krita-artists.org/u/tayete) at [Intermediate Palette Plugin Krita Forum Post](https://krita-artists.org/t/intermediate-palette-for-krita-docker/).
