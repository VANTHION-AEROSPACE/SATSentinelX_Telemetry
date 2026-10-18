# Local BMP280 patch provenance

## Evidence

The base is the locally cached Adafruit BMP280 Library 3.0.0 archive:

`C:\Users\Aaditya\AppData\Local\Arduino15\staging\libraries\Adafruit_BMP280_Library-3.0.0.zip`

Archive SHA-256:

`415531a76ae32f65290e23cf41b21360244259e953838dd7c4d5ff571283e02e`

The archive's `Adafruit_BMP280.cpp` SHA-256 is:

`a11a29248a1f30dfe5d4787f213426ca0abe4c9829dc19a6c7281c45021544a3`

The current vendored patched `.cpp` SHA-256 is:

`37d4cb8569072b947a1fd0cc694ed1db26b6441ad9c55a9ab66d57d89b1b2db8`

The canonical normalized unified diff generated from the two source trees is 9,841 bytes with SHA-256 `615ec320d7ad1287d3569cd8a2a3be34da79aba6597b496c94f4f68057df40f5`. The checked-in `Adafruit_BMP280_checked.patch` is a 1,641-byte human-readable patch manifest (SHA-256 `8fcf5424c911e1274410a6e22fd9c816eadfa52680582b568144b8ad25a62dfc`); the command below is the authoritative way to regenerate the full unified patch without embedding machine-specific paths.

The lockfile's expected `.cpp` hash, `C8CC5F4D3B43DF89448B509077B93C305EF240C0CF38F06A09FC2103BA2832C9`, has no recoverable provenance in Git, the local archive cache, or other repository copies. It remains unresolved and must not be replaced silently.

## Exact change set

The vendored source adds checked transaction wrappers for 8-bit, 16-bit, and 24-bit register operations; checked calibration/configuration/forced-measurement methods; and checked compensated temperature/pressure reads. `begin()` now fails when chip-ID, calibration, or initial configuration transactions fail. Legacy float/void APIs remain available.

Declarations and definitions match in `physical_demo/firmware/libraries/Adafruit_BMP280/Adafruit_BMP280.h` and `.cpp`. The implementation uses the existing Adafruit BusIO `write`, `write_then_read`, and SPI equivalents; no new external dependency is introduced.

The corrected sketch calls only the checked acquisition path. `measurement_verified` still means checked transaction/read success plus finite/range validation; it does not establish calibration accuracy or flight qualification.

## Reproduce and verify without modifying the repository

The following PowerShell procedure uses only a temporary directory. It does not overwrite the cached archive or vendored source:

```powershell
$archive = 'C:\Users\Aaditya\AppData\Local\Arduino15\staging\libraries\Adafruit_BMP280_Library-3.0.0.zip'
$tmp = Join-Path $env:TEMP ('satsentinel-bmp-provenance-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory($archive, $tmp)
$base = Join-Path $tmp 'Adafruit_BMP280_Library-3.0.0'
$current = Resolve-Path 'physical_demo/firmware/libraries/Adafruit_BMP280'
git diff --no-index -- $base/Adafruit_BMP280.h $current/Adafruit_BMP280.h
git diff --no-index -- $base/Adafruit_BMP280.cpp $current/Adafruit_BMP280.cpp
```

The two generated diffs are the canonical patch contents. A temporary reconstruction was performed from the cached archive using that normalized diff: the patch applied successfully, and both reconstructed files matched the vendored files byte-for-byte. The reconstructed header hash was `6bd6f0c1343a9e3627c82717f4b47ffe08d305b7394a27b2d336073f32343e86`; the reconstructed `.cpp` hash was the patched hash above.

## Remaining limitation

The repository can establish the exact base-to-current source difference, but it cannot establish who created the local checked-method patch or recover the lockfile's `C8CC...` source. This is local maintenance provenance, not upstream Adafruit authorship or an official release claim.
