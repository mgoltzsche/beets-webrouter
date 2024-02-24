# beets-webrouter

A [beets](https://github.com/beetbox/beets) plugin to serve multiple web apps on the same server/host/port with one command.

This allows serve the beets web UI, a Subsonic API as well as the generated M3U playlists with a single `beets webrouter` command.

## Installation

```sh
python3 -m pip install beets-webrouter
```

To install the plugins that are used by the example configuration below, run:
```sh
python3 -m pip install beets-beetstream beets-webm3u
```

## Configuration

Enable the plugin and add a `webrouter` section to your beets `config.yaml` as follows:
```yaml
plugins:
  - webrouter
  - web
  - webm3u
  - beetstream
  - aura
  - smartplaylist

webrouter:
  host: 127.0.0.1
  port: 8337
  routes:
    /:
      plugin: web
    /subsonic:
      plugin: beetstream
      config:
        never_transcode: true
    /aura:
      plugin: aura
      blueprint: aura_bp
    /m3u:
      plugin: webm3u

aura:
  page_limit: 100

smartplaylist:
  auto: false
  output: m3u
  playlist_dir: /data/playlists
  relative_to: /data/playlists
  playlists:
  - name: all.m3u
    query: ''
```

## Usage

Once the `webrouter` plugin is enabled within your beets configuration, you can run it as follows:
```sh
beet webrouter
```

You browse the server at [`http://localhost:8337`](http://localhost:8337).

### CLI

```
Usage: beet webrouter [options]
```

## Development

Run the unit tests (containerized):
```sh
make test
```

Run the e2e tests (containerized):
```sh
make test-e2e
```

To test your plugin changes manually, you can run a shell within a beets docker container as follows:
```sh
make beets-sh
```

A temporary beets library is written to `./data`.
It can be removed by calling `make clean-data`.

To just start the server, run:
```sh
make beets-webrouter
```
