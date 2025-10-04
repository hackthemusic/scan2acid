<img src="assets/s2a_light.png" alt="scan2acid logo" width="200"/>

# scan2acid

Generates 303-like sequences based on different events, such as network scans.
Scripts and files on the "dev_tests" folder are just for testing and/or learning purposes. They might work, or they might not.

## Dependencies

This project depends on the Python packages listed in `requirements.txt`.
Install them by running: 
```
pip install -r requirements.txt
```

This project is currently being used and tested on Ubuntu 25.04 with a Mackie Onyx Producer 2-2 audio + MIDI interface.

## Usage

This program uses an interactive CLI (so far; check next steps for more info). To run it, execute:
```bash
python scan2acid.py
```
From there, you can play demo sequences or parse already existing network scans (in nmap XML format). The tool also lets you sequence external gear (notes and clock sync).
You can also export the sequences in HTML format (for manual introduction in a DAW). MIDI and SYSEX export is planned for future releases (see: next steps).

You can always run the "help" command to get a list of available commands.

## Next steps

This tool is a working proof of concept of alternative ways of generating music. It is still in early development; in fact, it's just a 303-specific implementation of a general framework that we are working on. With that being said, for this specific 303 implementation, the next steps are the following:
- **Implementing MIDI and SYSEX export**. So far both work, but the exported notes are still not the right ones. As this was not a priority for RootedCON Valencia, it was left for future releases.
- **Implementing more event parsers**. So far, only nmap XML files are supported, but other formats (both statically and dynamically supplied) are planned.
- **Implementing control via arguments**: so far, the tool is interactive only. However, it would be nice to be able to run it with arguments (e.g., to parse a scan and export it to HTML in one command), and for automating this tool with other tools.
- **Implementing triplets and other rhythmic figures**. So far, only straight 16th notes are supported. 

## License

This project is licensed under the CC-BY-SA 4.0 License. To sum it up:

You are free to:
- Share — copy and redistribute the material in any medium or format for any purpose, even commercially.
- Adapt — remix, transform, and build upon the material for any purpose, even commercially.
- The licensor cannot revoke these freedoms as long as you follow the license terms.

Under the following terms:
- Attribution — You must give appropriate credit , provide a link to the license, and indicate if changes were made . You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.
- ShareAlike — If you remix, transform, or build upon the material, you must distribute your contributions under the same license as the original.
- No additional restrictions — You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.

For more details on this license, you can visit the [Creative Commons site](https://creativecommons.org/licenses/by-sa/4.0/) or read the full license text in the `LICENSE` file.

---

Happy (musical) hacking!
Made with <3 by Hack the Music.