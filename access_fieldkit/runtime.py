"""Prepare the pinned Java extractor on a local machine."""
import hashlib
import os
import subprocess
import urllib.request
from pathlib import Path

VERSION = "5.0.4"
# Checked against the JAR used in the Oracle VM run and the upstream release.
SHA256 = "19a7494a56f439a57fda85c059b019b665802085cec5ae8186d1e028cc1bdfbc"
URL = f"https://repo.maven.apache.org/maven2/com/healthmarketscience/jackcess/jackcess/{VERSION}/jackcess-{VERSION}.jar"
CACHE = Path.home() / ".cache" / "access-fieldkit" / VERSION
JAVA_SOURCE = Path(__file__).parent / "java" / "AccessReader.java"


def java_classpath(jar=None):
    cache = CACHE
    cache.mkdir(parents=True, exist_ok=True)
    if jar is not None:
        dependency = Path(jar).resolve()
        if not dependency.is_file():
            raise FileNotFoundError(f"Jackcess jar not found: {dependency}")
    else:
        dependency = cache / f"jackcess-{VERSION}.jar"
        if not dependency.exists():
            data = urllib.request.urlopen(URL, timeout=45).read()
            if not data.startswith(b"PK"):
                raise RuntimeError("Downloaded dependency was not a JAR")
            if hashlib.sha256(data).hexdigest() != SHA256:
                raise RuntimeError("Jackcess download failed SHA-256 verification")
            temp = dependency.with_suffix(".tmp")
            temp.write_bytes(data)
            temp.replace(dependency)
    if hashlib.sha256(dependency.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Jackcess JAR checksum mismatch: " + str(dependency))
    stamp = hashlib.sha256(JAVA_SOURCE.read_bytes() + str(dependency).encode() +
                           str(dependency.stat().st_size).encode()).hexdigest()
    classes = cache / "classes"
    marker = cache / "compile.sha256"
    if not (classes / "AccessReader.class").exists() or not marker.exists() or marker.read_text() != stamp:
        classes.mkdir(exist_ok=True)
        subprocess.run(["javac", "-encoding", "UTF-8", "-cp", str(dependency), "-d",
                        str(classes), str(JAVA_SOURCE)], check=True)
        marker.write_text(stamp)
    return os.pathsep.join((str(classes), str(dependency)))


def run_reader(mode, source, target, jar=None):
    cp = java_classpath(jar)
    subprocess.run(["java", "-cp", cp, "AccessReader", mode,
                    str(source), str(target)], check=True)
