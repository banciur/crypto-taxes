# crypto-taxes
Yet another unfinished system for tracking crypto transactions and calculating taxes. But I need something tailored for stable farmer in Germany.

## Development
### Python version
The minimum required Python version for this project is 3.13. I recommend using [pyenv](https://github.com/pyenv/pyenv) (along with the [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv) plugin) to manage and create virtual environments. While you can name the virtual environment however you like, it's good practice to include both the project name and the Python version

```bash
pyenv install 3.13
```
```bash
pyenv virtualenv 3.13 crypto-taxes-3.13
echo "crypto-taxes-3.13" > .python-version
```

### Dependencies
Note: If you're using macOS with the zsh shell, you need to escape "\[" and "\]" with "\\".
```bash
pip install --editable .
pip install --editable .\[dev\]
```