# Publishing this fork to PyPI

## 1. Choose the PyPI package name

The distribution name is set in `pyproject.toml` as **`bbmm-undetected-chromedriver`** so it does not clash with the original **`undetected-chromedriver`** on PyPI.

- Import in Python stays: `import undetected_chromedriver as uc`
- Install becomes: `pip install bbmm-undetected-chromedriver`

To use another name, edit the `name = "..."` field in `pyproject.toml` and ensure that name is **not** already taken on [pypi.org](https://pypi.org).

## 2. Set your repository URLs

If you publish from a different fork, update **`[project.urls]`** in `pyproject.toml` to match your GitHub org or username.

## 3. Bump the version

Edit `undetected_chromedriver/__init__.py` and set `__version__` (e.g. `3.6.1`). PyPI does not allow re-uploading the same version.

## 4. Build

```bash
cd /path/to/undetected-chromedriver
python3 -m pip install --upgrade build twine
python3 -m build
```

This creates `dist/*.whl` and `dist/*.tar.gz`.

## 5. Upload

**TestPyPI (recommended first):**

```bash
python3 -m twine upload --repository testpypi dist/*
```

Install from TestPyPI:

```bash
pip install -i https://test.pypi.org/simple/ bbmm-undetected-chromedriver
```

**Production PyPI:**

1. Create an account on [pypi.org](https://pypi.org) and [API token](https://pypi.org/manage/account/token/).
2. Configure `~/.pypirc` or use environment variables (see Twine docs).
3. Upload:

```bash
python3 -m twine upload dist/*
```

## 6. GPL-3.0

This project is under **GPL-3.0** (see `LICENSE`). Publishing a fork is allowed if you comply with the license (same license, state changes, etc.). This is not legal advice.

## 7. Optional: `.gitignore` for builds

Ensure `dist/`, `build/`, and `*.egg-info/` are in `.gitignore` (they usually are).
