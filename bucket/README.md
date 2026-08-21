# Scoop bucket

This folder is the Scoop bucket for Gladius:

```
scoop bucket add gladius https://github.com/BrianZodd/Gladius
scoop install gladius/gladius
```

`gladius.json` is **generated, not hand-written.** The release workflow renders it from
`packaging/scoop/gladius.json` using the SHA256 of the artifact it just published, then
commits it here — so the manifest can never disagree with the file users actually
download.

That is also why it is absent until the first release: a manifest committed with a
locally-built hash would be wrong the moment CI rebuilt the artifact (PyInstaller output
is not byte-reproducible), and Scoop would refuse the install over a hash mismatch. An
empty bucket is honest; a wrong one wastes somebody's afternoon.

To produce one by hand for testing:

```bash
python packaging/build.py
python packaging/render_manifests.py --from-dist
cp dist/manifests/scoop/gladius.json bucket/
```
