/* app.js — MiSTer BIOS Checker UI */
(function () {
  'use strict';

  // Theme toggle: cycles auto -> light -> dark
  var themeBtn = document.getElementById('theme-toggle');
  var themes = ['auto', 'light', 'dark'];
  var themeLabels = { auto: 'Auto', light: 'Light', dark: 'Dark' };
  var currentTheme = localStorage.getItem('theme') || 'auto';
  function applyTheme(t) {
    currentTheme = t;
    localStorage.setItem('theme', t);
    if (t === 'auto') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', t);
    }
    themeBtn.textContent = themeLabels[t];
  }
  applyTheme(currentTheme);
  themeBtn.addEventListener('click', function () {
    var idx = (themes.indexOf(currentTheme) + 1) % themes.length;
    applyTheme(themes[idx]);
  });

  var state = {
    entries: [],
    meta: null,
    scanResults: {},  // target_path -> { status, actualMd5? }
    filter: 'all',
    search: '',
  };

  var el = {
    content: document.getElementById('content'),
    loading: document.getElementById('loading'),
    search: document.getElementById('search'),
    filters: document.getElementById('filters'),
    scanBtn: document.getElementById('scan-btn'),
    folderBtn: document.getElementById('folder-btn'),
    clearBtn: document.getElementById('clear-btn'),
    dirInput: document.getElementById('dir-input'),
    dropZone: document.getElementById('drop-zone'),
    scanProgress: document.getElementById('scan-progress'),
    scanSummary: document.getElementById('scan-summary'),
    countTotal: document.getElementById('count-total'),
    countCores: document.getElementById('count-cores'),
    countRetrobios: document.getElementById('count-retrobios'),
  };

  // Helpers

  function setText(node, text) { node.textContent = text; }

  function makeEl(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  // Data loading

  function load() {
    return fetch('data/bios.json').then(function (r) {
      if (!r.ok) throw new Error('failed to load bios.json');
      return r.json();
    }).then(function (data) {
      state.entries = data.entries;
      return fetch('data/meta.json').then(function (r) { return r.json(); });
    }).then(function (meta) {
      state.meta = meta;
      setText(el.countTotal, meta.counts.total);
      setText(el.countCores, meta.counts.cores);
      setText(el.countRetrobios, meta.counts.retrobios_matched || 0);
      el.loading.classList.add('hidden');
      render();
    }).catch(function (err) {
      setText(el.loading, 'Failed to load BIOS catalog: ' + err.message);
    });
  }

  // Rendering

  function effectiveStatus(entry) {
    if (entry.source === 'gap') return 'gap';
    var r = state.scanResults[entry.target_path];
    if (!r) {
      if (entry.source === 'recipe') return 'recipe';
      return 'catalog';
    }
    return r.status;  // 'ok' | 'missing' | 'wrong'
  }

  function visible(entry) {
    var status = effectiveStatus(entry);
    if (state.filter !== 'all') {
      if (state.filter === 'ok' && status !== 'ok') return false;
      if (state.filter === 'missing' && status !== 'missing') return false;
      if (state.filter === 'wrong' && status !== 'wrong') return false;
      if (state.filter === 'gap' && status !== 'gap') return false;
    }
    if (state.search) {
      var s = state.search.toLowerCase();
      var hay = (entry.core + ' ' + entry.filename + ' ' + (entry.md5 || '') + ' ' +
                 entry.target_path + ' ' + (entry.notes || '')).toLowerCase();
      if (hay.indexOf(s) === -1) return false;
    }
    return true;
  }

  function formatSize(bytes) {
    if (bytes == null) return '?';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(2) + ' MB';
  }

  function renderCard(entry) {
    var card = document.createElement('div');
    var status = effectiveStatus(entry);
    card.className = 'card status-' + status;

    var head = makeEl('div', 'card-head');
    head.appendChild(makeEl('div', 'card-filename', entry.filename));

    var badgeLabel = {
      ok: 'Present',
      missing: 'Missing',
      wrong: 'Wrong hash',
      gap: 'Gap',
      recipe: 'Recipe',
      catalog: entry.source === 'extras' ? 'Extras' : 'Catalog',
    }[status];
    head.appendChild(makeEl('span', 'badge badge-' + status, badgeLabel));
    card.appendChild(head);

    var meta = makeEl('div', 'card-meta');
    meta.appendChild(document.createTextNode('Path: '));
    meta.appendChild(makeEl('code', null, entry.target_path));
    meta.appendChild(document.createTextNode(' · ' + formatSize(entry.size)));
    card.appendChild(meta);

    if (entry.md5) {
      var hash = makeEl('div', 'card-hash');
      hash.appendChild(makeEl('span', 'hash-value', entry.md5));
      var cb = makeEl('button', 'copy-btn', 'copy');
      cb.addEventListener('click', function () {
        navigator.clipboard.writeText(entry.md5).then(function () {
          cb.classList.add('copied');
          setText(cb, 'copied');
          setTimeout(function () {
            cb.classList.remove('copied');
            setText(cb, 'copy');
          }, 1200);
        });
      });
      hash.appendChild(cb);
      card.appendChild(hash);
    }

    if (status === 'wrong') {
      var r = state.scanResults[entry.target_path];
      var wh = makeEl('div', 'card-wrong-hash');
      wh.appendChild(document.createTextNode('Your file hashes to:'));
      wh.appendChild(document.createElement('br'));
      wh.appendChild(document.createTextNode(r.actualMd5));
      card.appendChild(wh);
    }

    var actions = makeEl('div', 'card-actions');
    if (entry.md5) {
      var gLink = makeEl('a', null, 'Google hash');
      gLink.href = 'https://www.google.com/search?q=' + encodeURIComponent('"' + entry.md5 + '"');
      gLink.target = '_blank';
      gLink.rel = 'noopener';
      actions.appendChild(gLink);
    } else {
      var gNameLink = makeEl('a', null, 'Google filename');
      gNameLink.href = 'https://www.google.com/search?q=' + encodeURIComponent('MiSTer ' + entry.core + ' ' + entry.filename + ' BIOS');
      gNameLink.target = '_blank';
      gNameLink.rel = 'noopener';
      actions.appendChild(gNameLink);
    }
    if (entry.url) {
      var uLink = makeEl('a', null, 'archive.org');
      uLink.href = entry.url;
      uLink.target = '_blank';
      uLink.rel = 'noopener';
      uLink.title = 'Download from archive.org (BiosDB mirror)';
      actions.appendChild(uLink);
    }
    if (entry.retrobios_url) {
      var rbLink = makeEl('a', null, 'retrobios');
      rbLink.href = entry.retrobios_url;
      rbLink.target = '_blank';
      rbLink.rel = 'noopener';
      rbLink.title = 'Download from retrobios (as ' + (entry.retrobios_name || 'file') + ')';
      actions.appendChild(rbLink);
    }
    if (entry.research_urls && entry.research_urls.length) {
      entry.research_urls.forEach(function (u, i) {
        var a = makeEl('a', null, 'research' + (entry.research_urls.length > 1 ? ' ' + (i + 1) : ''));
        a.href = u;
        a.target = '_blank';
        a.rel = 'noopener';
        actions.appendChild(a);
      });
    }
    card.appendChild(actions);

    if (entry.recipe && entry.recipe.variants && entry.recipe.variants.length) {
      card.appendChild(renderRecipe(entry));
    }

    if (entry.notes) {
      card.appendChild(makeEl('div', 'card-note', entry.notes));
    }

    return card;
  }

  function renderRecipe(entry) {
    var recipe = entry.recipe;
    var box = makeEl('div', 'card-recipe');

    var label = makeEl('div', 'recipe-label', 'Build from components (via retrobios):');
    box.appendChild(label);

    var select = makeEl('select', 'recipe-select');
    recipe.variants.forEach(function (v, i) {
      var opt = document.createElement('option');
      opt.value = i;
      opt.textContent = v.name;
      select.appendChild(opt);
    });
    box.appendChild(select);

    var buildBtn = makeEl('button', 'btn btn-recipe', 'Build ' + entry.filename);
    var statusEl = makeEl('div', 'recipe-status');

    buildBtn.addEventListener('click', function () {
      var idx = parseInt(select.value, 10);
      var variant = recipe.variants[idx];
      buildBtn.disabled = true;
      setText(buildBtn, 'Building…');
      setText(statusEl, '');
      assembleRecipe(variant, entry.filename).then(function (result) {
        if (result.error) {
          setText(statusEl, 'Error: ' + result.error);
          statusEl.className = 'recipe-status recipe-error';
        } else {
          setText(statusEl, 'Built! MD5: ' + result.md5 + (result.verified ? ' (verified)' : ' (MISMATCH)'));
          statusEl.className = 'recipe-status ' + (result.verified ? 'recipe-ok' : 'recipe-warn');
          triggerDownload(result.blob, entry.filename);
        }
        buildBtn.disabled = false;
        setText(buildBtn, 'Build ' + entry.filename);
      });
    });
    box.appendChild(buildBtn);
    box.appendChild(statusEl);
    return box;
  }

  function assembleRecipe(variant, filename) {
    var components = variant.components;
    var fetches = components.map(function (comp) {
      if (comp.type === 'zeros') {
        return Promise.resolve(new Uint8Array(comp.size));
      }
      if (comp.type === 'url') {
        return fetch(comp.url).then(function (r) {
          if (!r.ok) throw new Error('fetch failed: ' + comp.url + ' (' + r.status + ')');
          return r.arrayBuffer();
        }).then(function (buf) {
          var bytes = new Uint8Array(buf);
          if (comp.md5) {
            var actualMd5 = window.md5Bytes(bytes);
            if (actualMd5 !== comp.md5) {
              throw new Error('component MD5 mismatch for ' + (comp.label || comp.url) +
                ': expected ' + comp.md5 + ', got ' + actualMd5);
            }
          }
          return bytes;
        });
      }
      return Promise.reject(new Error('unknown component type: ' + comp.type));
    });

    return Promise.all(fetches).then(function (parts) {
      var totalSize = parts.reduce(function (s, p) { return s + p.length; }, 0);
      var assembled = new Uint8Array(totalSize);
      var offset = 0;
      parts.forEach(function (p) {
        assembled.set(p, offset);
        offset += p.length;
      });
      var md5 = window.md5Bytes(assembled);
      var verified = md5 === variant.md5;
      return {
        blob: new Blob([assembled], { type: 'application/octet-stream' }),
        md5: md5,
        verified: verified,
      };
    }).catch(function (err) {
      return { error: err.message };
    });
  }

  function triggerDownload(blob, filename) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      document.body.removeChild(a);
    }, 100);
  }

  function render() {
    while (el.content.firstChild) el.content.removeChild(el.content.firstChild);
    var byCore = {};
    state.entries.forEach(function (e) {
      if (!visible(e)) return;
      (byCore[e.core] = byCore[e.core] || []).push(e);
    });

    var cores = Object.keys(byCore).sort(function (a, b) {
      return a.toLowerCase().localeCompare(b.toLowerCase());
    });

    if (cores.length === 0) {
      var empty = makeEl('div', 'card-note', 'No entries match your filter.');
      empty.style.textAlign = 'center';
      empty.style.padding = '2rem';
      el.content.appendChild(empty);
      return;
    }

    cores.forEach(function (core) {
      var section = makeEl('section', 'core-section');
      var header = makeEl('div', 'core-header');
      header.appendChild(makeEl('h2', null, core));
      header.appendChild(makeEl('span', 'path', 'games/' + core + '/'));
      var countText = byCore[core].length + (byCore[core].length === 1 ? ' entry' : ' entries');
      header.appendChild(makeEl('span', 'core-count', countText));
      section.appendChild(header);

      var cards = makeEl('div', 'cards');
      byCore[core].forEach(function (entry) {
        cards.appendChild(renderCard(entry));
      });
      section.appendChild(cards);
      el.content.appendChild(section);
    });
  }

  function updateScanSummary() {
    var counts = { ok: 0, missing: 0, wrong: 0, gap: 0, catalog: 0 };
    state.entries.forEach(function (e) { counts[effectiveStatus(e)]++; });
    var hasResults = Object.keys(state.scanResults).length > 0;
    if (!hasResults) {
      el.scanSummary.classList.add('hidden');
      el.clearBtn.classList.add('hidden');
      return;
    }
    el.scanSummary.classList.remove('hidden');
    el.clearBtn.classList.remove('hidden');
    while (el.scanSummary.firstChild) el.scanSummary.removeChild(el.scanSummary.firstChild);
    el.scanSummary.appendChild(document.createTextNode('· '));
    el.scanSummary.appendChild(makeEl('span', 'count count-ok', counts.ok + ' present'));
    el.scanSummary.appendChild(document.createTextNode(' · '));
    el.scanSummary.appendChild(makeEl('span', 'count count-err', counts.missing + ' missing'));
    el.scanSummary.appendChild(document.createTextNode(' · '));
    el.scanSummary.appendChild(makeEl('span', 'count count-warn', counts.wrong + ' wrong hash'));
  }

  // SD card scanning

  function indexFiles(files) {
    var index = {};
    for (var i = 0; i < files.length; i++) {
      var f = files[i];
      var p = f.webkitRelativePath || f.name;
      index[p.toLowerCase()] = f;
    }
    return index;
  }

  function findEntryFile(entry, pathIndex, pathList) {
    var needle = entry.target_path.toLowerCase();
    if (pathIndex[needle]) return pathIndex[needle];
    var suffix = '/' + needle;
    for (var i = 0; i < pathList.length; i++) {
      if (pathList[i].endsWith(suffix) || pathList[i] === needle) {
        return pathIndex[pathList[i]];
      }
    }
    return null;
  }

  function hashFile(file) {
    return file.arrayBuffer().then(function (buf) {
      return window.md5Bytes(new Uint8Array(buf));
    });
  }

  function runScan(fileList) {
    var pathIndex = indexFiles(fileList);
    var pathList = Object.keys(pathIndex);
    state.scanResults = {};

    var hashable = state.entries.filter(function (e) { return e.md5; });
    var total = hashable.length;
    var done = 0;

    el.scanProgress.classList.remove('hidden');
    setText(el.scanProgress, 'Scanning ' + total + ' BIOS targets…');

    return hashable.reduce(function (promise, entry) {
      return promise.then(function () {
        var file = findEntryFile(entry, pathIndex, pathList);
        if (!file) {
          state.scanResults[entry.target_path] = { status: 'missing' };
          done++;
          if (done % 5 === 0) {
            setText(el.scanProgress, 'Scanning ' + done + '/' + total + '…');
          }
          return;
        }
        return hashFile(file).then(function (actualMd5) {
          state.scanResults[entry.target_path] = (actualMd5 === entry.md5)
            ? { status: 'ok' }
            : { status: 'wrong', actualMd5: actualMd5 };
          done++;
          setText(el.scanProgress, 'Scanning ' + done + '/' + total + ' — ' + entry.core + '/' + entry.filename);
        });
      });
    }, Promise.resolve()).then(function () {
      el.scanProgress.classList.add('hidden');
      updateScanSummary();
      render();
    });
  }

  // Folder picker (File System Access API with fallback)

  function pickFolder() {
    if (window.showDirectoryPicker) {
      return window.showDirectoryPicker().then(function (dirHandle) {
        return collectFromDirHandle(dirHandle);
      }).then(runScan).catch(function (err) {
        if (err && err.name !== 'AbortError') console.warn('picker error:', err);
      });
    }
    el.dirInput.click();
  }

  function collectFromDirHandle(dirHandle, prefix) {
    prefix = prefix || dirHandle.name;
    return (async function () {
      var out = [];
      for await (var entry of dirHandle.entries()) {
        var name = entry[0];
        var handle = entry[1];
        var subpath = prefix + '/' + name;
        if (handle.kind === 'file') {
          var f = await handle.getFile();
          Object.defineProperty(f, 'webkitRelativePath', { value: subpath, configurable: true });
          out.push(f);
        } else if (handle.kind === 'directory') {
          var sub = await collectFromDirHandle(handle, subpath);
          for (var i = 0; i < sub.length; i++) out.push(sub[i]);
        }
      }
      return out;
    })();
  }

  // Drag and drop

  function handleDrop(e) {
    e.preventDefault();
    el.dropZone.classList.remove('drag-over');
    var items = e.dataTransfer.items;
    if (!items || items.length === 0) return;
    var promises = [];
    for (var i = 0; i < items.length; i++) {
      var entry = items[i].webkitGetAsEntry && items[i].webkitGetAsEntry();
      if (entry) promises.push(walkEntry(entry, entry.name));
    }
    Promise.all(promises).then(function (lists) {
      var all = [];
      lists.forEach(function (l) { l.forEach(function (f) { all.push(f); }); });
      if (all.length > 0) runScan(all);
    });
  }

  function walkEntry(entry, path) {
    return new Promise(function (resolve) {
      if (entry.isFile) {
        entry.file(function (file) {
          Object.defineProperty(file, 'webkitRelativePath', { value: path, configurable: true });
          resolve([file]);
        }, function () { resolve([]); });
      } else if (entry.isDirectory) {
        var reader = entry.createReader();
        var all = [];
        var readBatch = function () {
          reader.readEntries(function (entries) {
            if (entries.length === 0) {
              resolve(all);
              return;
            }
            Promise.all(entries.map(function (e) {
              return walkEntry(e, path + '/' + e.name);
            })).then(function (results) {
              results.forEach(function (r) { r.forEach(function (f) { all.push(f); }); });
              readBatch();
            });
          }, function () { resolve(all); });
        };
        readBatch();
      } else {
        resolve([]);
      }
    });
  }

  // Folder template ZIP download

  function generateFolderZip() {
    if (!state.entries.length) return;

    // Group entries by core
    var byCore = {};
    state.entries.forEach(function (e) {
      (byCore[e.core] = byCore[e.core] || []).push(e);
    });

    // Build file list for the zip: one _BIOS_INFO.txt per core folder
    var files = [];
    Object.keys(byCore).sort(function (a, b) {
      return a.toLowerCase().localeCompare(b.toLowerCase());
    }).forEach(function (core) {
      var entries = byCore[core];
      var lines = [
        core + ' — MiSTer BIOS files needed',
        '='.repeat(core.length + 30),
        '',
        'Place these files in /media/fat/games/' + core + '/ on your MiSTer SD card.',
        'To find a file, Google its MD5 hash.',
        '',
      ];
      entries.forEach(function (e) {
        lines.push('  ' + e.filename);
        if (e.size) lines.push('    Size: ' + formatSize(e.size) + ' (' + e.size + ' bytes)');
        if (e.md5) lines.push('    MD5:  ' + e.md5);
        if (e.notes) lines.push('    Note: ' + e.notes);
        lines.push('');
      });
      lines.push('Generated by MiSTer FPGA BIOS Checker');
      lines.push('https://takiiiiiii.github.io/MiSTerFPGA-BIOS/');
      var content = lines.join('\n');
      files.push({ name: 'games/' + core + '/_BIOS_INFO.txt', data: content });
    });

    var blob = buildZip(files);
    triggerDownload(blob, 'MiSTer_BIOS_folders.zip');
  }

  // Builds an uncompressed ZIP from an array of {name, data} text files
  function buildZip(files) {
    var localHeaders = [];
    var centralHeaders = [];
    var offset = 0;

    files.forEach(function (file) {
      var nameBytes = new TextEncoder().encode(file.name);
      var dataBytes = new TextEncoder().encode(file.data);
      var crc = crc32(dataBytes);

      // Local file header (30 bytes + name + data)
      var local = new Uint8Array(30 + nameBytes.length + dataBytes.length);
      var lv = new DataView(local.buffer);
      lv.setUint32(0, 0x04034b50, true);  // signature
      lv.setUint16(4, 20, true);           // version needed
      lv.setUint16(6, 0, true);            // flags
      lv.setUint16(8, 0, true);            // compression (STORE)
      lv.setUint16(10, 0, true);           // mod time
      lv.setUint16(12, 0, true);           // mod date
      lv.setUint32(14, crc, true);         // crc32
      lv.setUint32(18, dataBytes.length, true); // compressed size
      lv.setUint32(22, dataBytes.length, true); // uncompressed size
      lv.setUint16(26, nameBytes.length, true); // name length
      lv.setUint16(28, 0, true);           // extra length
      local.set(nameBytes, 30);
      local.set(dataBytes, 30 + nameBytes.length);
      localHeaders.push(local);

      // Central directory header (46 bytes + name)
      var central = new Uint8Array(46 + nameBytes.length);
      var cv = new DataView(central.buffer);
      cv.setUint32(0, 0x02014b50, true);   // signature
      cv.setUint16(4, 20, true);           // version made by
      cv.setUint16(6, 20, true);           // version needed
      cv.setUint16(8, 0, true);            // flags
      cv.setUint16(10, 0, true);           // compression
      cv.setUint16(12, 0, true);           // mod time
      cv.setUint16(14, 0, true);           // mod date
      cv.setUint32(16, crc, true);         // crc32
      cv.setUint32(20, dataBytes.length, true);
      cv.setUint32(24, dataBytes.length, true);
      cv.setUint16(28, nameBytes.length, true);
      cv.setUint16(30, 0, true);           // extra length
      cv.setUint16(32, 0, true);           // comment length
      cv.setUint16(34, 0, true);           // disk number
      cv.setUint16(36, 0, true);           // internal attrs
      cv.setUint32(38, 0, true);           // external attrs
      cv.setUint32(42, offset, true);      // local header offset
      central.set(nameBytes, 46);
      centralHeaders.push(central);

      offset += local.length;
    });

    var centralOffset = offset;
    var centralSize = centralHeaders.reduce(function (s, c) { return s + c.length; }, 0);

    // End of central directory (22 bytes)
    var ecd = new Uint8Array(22);
    var ev = new DataView(ecd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(4, 0, true);
    ev.setUint16(6, 0, true);
    ev.setUint16(8, files.length, true);
    ev.setUint16(10, files.length, true);
    ev.setUint32(12, centralSize, true);
    ev.setUint32(16, centralOffset, true);
    ev.setUint16(20, 0, true);

    var parts = localHeaders.concat(centralHeaders, [ecd]);
    return new Blob(parts, { type: 'application/zip' });
  }

  // CRC32 (needed by ZIP format)
  function crc32(bytes) {
    var table = crc32.table;
    if (!table) {
      table = crc32.table = new Uint32Array(256);
      for (var i = 0; i < 256; i++) {
        var c = i;
        for (var j = 0; j < 8; j++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
        table[i] = c;
      }
    }
    var crc = 0xFFFFFFFF;
    for (var k = 0; k < bytes.length; k++) {
      crc = table[(crc ^ bytes[k]) & 0xFF] ^ (crc >>> 8);
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }

  // Wire up UI events

  el.scanBtn.addEventListener('click', pickFolder);

  el.folderBtn.addEventListener('click', function () {
    generateFolderZip();
  });

  el.clearBtn.addEventListener('click', function () {
    state.scanResults = {};
    updateScanSummary();
    render();
  });

  el.dirInput.addEventListener('change', function (e) {
    if (e.target.files && e.target.files.length > 0) {
      runScan(e.target.files);
    }
  });

  el.search.addEventListener('input', function (e) {
    state.search = e.target.value.trim();
    render();
  });

  el.filters.addEventListener('click', function (e) {
    if (e.target.classList.contains('chip')) {
      Array.prototype.forEach.call(el.filters.querySelectorAll('.chip'), function (c) {
        c.classList.remove('active');
      });
      e.target.classList.add('active');
      state.filter = e.target.dataset.filter;
      render();
    }
  });

  ['dragenter', 'dragover'].forEach(function (evt) {
    window.addEventListener(evt, function (e) {
      e.preventDefault();
      el.dropZone.classList.add('drag-over');
    });
  });
  ['dragleave', 'dragend'].forEach(function (evt) {
    window.addEventListener(evt, function (e) {
      if (e.target === el.dropZone || e.target === document.body || e.target === document.documentElement) {
        el.dropZone.classList.remove('drag-over');
      }
    });
  });
  window.addEventListener('drop', handleDrop);

  load();
})();
