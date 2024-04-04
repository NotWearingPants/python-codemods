# Python Codemods

Python codemods implemented using [LibCST](https://github.com/Instagram/LibCST).

## How to Use

```sh
pip3 install libcst
git clone ...
cd ./python-codemods/
python3 -m libcst.tool codemod -x codemods.<name of a codemod file>.Run /path/to/src/
```
