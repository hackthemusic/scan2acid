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
python3 scan2acid.py
```
From there, you can play demo sequences or parse already existing network scans (in nmap XML format). The tool also lets you sequence external gear (notes and clock sync).
You can also export the sequences in HTML format (for manual introduction in a DAW). MIDI and SYSEX export is planned for future releases (see: next steps).

You can always run the "help" command to get a list of available commands.<br>

There's ways to customize the scales you can generate notes from, as well as the keywords for the accent steps. Respectively, you might want to take a deeper look into the `scales.conf` and `keywords.conf` files :^)

## Note generation algorithm

Note generation is based (almost) entirely on the results of an nmap scan (as of now, in XML format): `nmap (target) -sV --top-ports 16 --open -oX (file.xml)`. <br>
In order to determine the sequence length (so far, 8 or 16 steps), we take the amount of open ports discovered:
- If port_amount <= 8, then seq_len = 8
- If port_amount > 8, then seq_len = 16

Once a sequence of a certain length is created, it is filled with as many active steps as ports have been discovered and as many rest steps as necesary in order to fill the entire sequence. For example:
- If we've discovered 6 ports with the nmap scan, seq_len will be 8. Out of these 8 steps, 6 will be active and 2 will be rest.
- If we've discovered 12 ports, seq_len will be 16. Out of these, 12 will be active and 4 will be rest.

In both cases, the rest steps' indexes are randomly assigned to steps within the sequence. <br><br>
With that part figured out, we now have to decide what notes to assign to the steps.<br>
The active steps' notes in the sequence are calculated using the following code fragment:
```python
degree = service.port % len(scale_notes)
note = (int(scale_notes[degree])) + OCT_SHIFT # shift to a more reasonable octave
# scale_notes is a list that contains values obtained from the scales.conf file, customizable by the user
```
The above formula obtains the position of the note on the scale based on the result of the port number modulus between the length of the scale determined.
Then, its value is normalized by adding 3 octaves (constant “OCT_SHIFT”; remember that, by default, scales are defined in octave 0, which are notes that are too low).<br><br>

We don't forget about accents, though! These are determined depending if the port service info associated to the step contains one or more keywords as defined in the `keywords.conf` file. For example, you might wanna look for certain Apache2 versions, certain Windows versions or certain strings in banners that might be of interest for your sequence (or engagement!).<br><br>

We don't forget about tie steps, either! These are a special type of step that is longer than a standard one, thus creating a pitch slide effect between notes. Steps which information is greater in length than a predefined value (as defined on `TIE_THRESHOLD = 30` by default on `scan2acid.py`) will be automatically asigned a tie length.<br><br>
And last but not least: octave jumps are the only truly randomized parameter in this algorithm. We kept it that way in order to promote the generation of cool, unexpected, happy accidents.<br><br>

Please note this is a work-in-progress; the algorithm will probably be improved in the future. However, it is usable and playable right now, which is the reason why we wanted to publish it. Have fun!

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
