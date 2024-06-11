try:
    import __version__
except:
    import electrum.plugins.BalPlugin.__version__ as __version__
def version():
    out = "0"
    try:
        with open(__version__.__file__,"r") as f:
            out = str(f.read()).strip()
    except:
        pass
    return out
