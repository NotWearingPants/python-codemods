# Python Codemods

Python codemods implemented using [LibCST](https://github.com/Instagram/LibCST).

## How to Use

```sh
pip3 install libcst
git clone ... ./python_codemods/
python3 -m libcst.tool codemod -x python_codemods.codemods.<name of a codemod file>.Run /path/to/src/
```
