/* =============================================================================
   YouTube Downloader — frontend
   Vanilla JS, no build step. Handles info fetching, format presets, the job
   queue with live progress, download history, PWA registration and i18n (EN/BN).
   ========================================================================== */
(() => {
  'use strict';

  /* ------------------------------------------------------------------ i18n */
  const I18N = {
    en: {
      'app.name': 'YouTube Downloader',
      'app.tagline': 'Fast • Free • High quality',
      'hero.badge': 'Videos • MP3 • Playlists • Subtitles',
      'hero.title': 'Download YouTube videos',
      'hero.highlight': 'Fast • Free • High quality',
      'hero.subtitle': 'Paste a link, pick a quality and save the file. Everything runs on your own server.',
      'demo.banner': 'Demo mode is on: sample data is used and nothing is sent to YouTube.',

      'input.label': 'YouTube URL',
      'input.placeholder': 'https://www.youtube.com/watch?v=...',
      'input.getInfo': 'Get info',
      'input.hint': 'Supports videos, Shorts, live replays and playlists. Paste several links (one per line) for batch download.',

      'batch.hint': 'All links are queued with the settings below.',
      'batch.preset': 'Quality for all links',
      'batch.count': '{n} links detected',
      'batch.added': '{n} links added to the queue',

      'btn.download': 'Download',
      'btn.selectAll': 'Select all',
      'btn.selectNone': 'Clear selection',
      'btn.saveThumbnail': 'Save thumbnail',
      'btn.openYouTube': 'Open on YouTube',
      'btn.showAdvanced': 'Advanced options',
      'btn.addToQueue': 'Add {n} links to queue',
      'btn.downloadSelected': 'Download selected ({n})',
      'btn.cancel': 'Cancel',
      'btn.remove': 'Remove',
      'btn.retry': 'Retry',
      'btn.saveFile': 'Save file',
      'btn.downloadAgain': 'Download again',
      'btn.clear': 'Clear',

      'section.options': 'Choose what to download',
      'section.queue': 'Download queue',
      'section.history': 'History',
      'section.subtitles': 'Subtitles',
      'section.trim': 'Trim / cut',
      'section.format': 'Exact format',
      'section.filename': 'File name (optional)',
      'section.playlist': 'Playlist',

      'preset.best': 'Best quality',
      'preset.best.desc': 'Highest video + audio',
      'preset.mp4': 'MP4 (H.264)',
      'preset.mp4.desc': 'Plays on any device',
      'preset.video.desc': 'Video + audio',
      'preset.audioMp3': 'MP3 audio',
      'preset.audioMp3.desc': '192 kbps · MP3',
      'preset.audioM4a': 'M4A audio',
      'preset.audioM4a.desc': 'Original AAC',
      'preset.subtitles': 'Subtitles only',
      'preset.subtitles.desc': 'SRT / VTT file',
      'preset.custom': 'Custom format',
      'preset.custom.desc': 'Pick from the list',
      'preset.audio.desc': '{format} · {quality} kbps',

      'opt.audioFormat': 'Audio format',
      'opt.audioQuality': 'Audio quality',
      'opt.noConvert': 'Original (no convert)',
      'opt.subtitleFormat': 'Subtitle format',
      'opt.subtitleLang': 'Subtitle language',
      'opt.subsNone': 'No subtitles',
      'opt.embedSubs': 'Embed subtitles into the video',
      'opt.noSubs': 'No subtitles are available for this video.',
      'opt.noFormats': 'No downloadable formats were found for this video.',
      'opt.playlistQuality': 'Quality for all',
      'opt.trimStart': 'Start time',
      'opt.trimEnd': 'End time',
      'opt.trimHint': 'Example: 1:30 or 90 (seconds). Leave empty to download the whole video.',
      'opt.filenamePlaceholder': 'Custom file name',
      'opt.ffmpegMissing': 'ffmpeg is not installed on the server, so MP3 conversion, trimming and format merging are disabled.',

      'status.queued': 'In queue',
      'status.preparing': 'Preparing',
      'status.downloading': 'Downloading',
      'status.processing': 'Processing',
      'status.completed': 'Ready to save',
      'status.failed': 'Failed',
      'status.canceled': 'Canceled',

      'queue.empty': 'No downloads yet. Paste a link above to get started.',
      'queue.clearFinished': 'Clear finished',
      'queue.eta': 'ETA',
      'queue.entry': '{i}/{n}',
      'queue.files': '{n} files',
      'queue.speed': 'Speed',

      'history.empty': 'Nothing here yet.',
      'history.clear': 'Clear history',
      'history.confirmClear': 'Clear the entire download history?',
      'history.expired': 'Files are deleted from the server after {time}.',
      'history.removed': 'Removed from history',

      'playlist.selected': '{n} selected',
      'playlist.truncated': 'Only the first {n} videos can be listed.',
      'playlist.empty': 'This playlist has no downloadable videos.',

      'mode.video': 'Video',
      'mode.audio': 'Audio',
      'mode.subtitles': 'Subtitles',

      'toast.downloadStarted': 'Download added to the queue',
      'toast.completed': 'Ready to save: {name}',
      'toast.failed': 'Download failed: {message}',
      'toast.canceled': 'Download canceled',
      'toast.queued': 'Added to the queue',
      'toast.thumbnailSaved': 'Thumbnail saved',
      'toast.offline': 'You are offline. New downloads will not work.',

      'err.emptyUrl': 'Please paste a YouTube link first.',
      'err.invalid_trim': 'Please check the trim times (example: 1:30).',
      'err.noSubtitleSelected': 'Choose at least one subtitle language.',
      'err.invalid_url': 'Please paste a valid YouTube link.',
      'err.invalid_request': 'Some of the options are not valid. Please check them.',
      'err.ffmpeg_missing': 'This feature needs ffmpeg on the server.',
      'err.private_video': 'This video is private or requires sign-in.',
      'err.age_restricted': 'This video is age restricted and cannot be downloaded.',
      'err.unavailable': 'This video is unavailable or was removed.',
      'err.network': 'Could not reach YouTube. Please check your connection.',
      'err.extract_failed': 'Could not read this video. It may be restricted.',
      'err.format_unavailable': 'That quality is not available for this video.',
      'err.no_file': 'The download finished but no file was produced.',
      'err.queue_full': 'The queue is full. Please wait for it to finish.',
      'err.rate_limited': 'Too many requests. Please wait a moment.',
      'err.job_not_found': 'This download is no longer available.',
      'err.job_not_ready': 'This download is still running.',
      'err.file_expired': 'This file has expired. Please download again.',
      'err.no_subtitles': 'No subtitle language was selected.',
      'err.thumbnail_failed': 'Could not fetch the thumbnail.',
      'err.download_failed': 'The download failed. Please try again.',
      'err.http_error': 'The request failed. Please try again.',
      'err.unknown': 'Something went wrong. Please try again.',

      'aria.theme': 'Toggle dark / light mode',
      'aria.language': 'Change language',
      'footer.disclaimer': 'For personal and educational use only. Respect copyright and YouTube’s Terms of Service.',
      'footer.builtWith': 'Built with FastAPI + yt-dlp',
    },

    bn: {
      'app.name': 'ইউটিউব ডাউনলোডার',
      'app.tagline': 'দ্রুত • ফ্রি • উচ্চ মান',
      'hero.badge': 'ভিডিও • MP3 • প্লেলিস্ট • সাবটাইটেল',
      'hero.title': 'ইউটিউব ভিডিও ডাউনলোড করুন',
      'hero.highlight': 'দ্রুত • ফ্রি • উচ্চ মান',
      'hero.subtitle': 'লিংক পেস্ট করুন, কোয়ালিটি বেছে নিন আর ফাইল সেভ করুন। সবকিছু আপনার নিজের সার্ভারে চলে।',
      'demo.banner': 'ডেমো মোড চালু আছে: নমুনা ডেটা ব্যবহৃত হচ্ছে, ইউটিউবে কিছু পাঠানো হচ্ছে না।',

      'input.label': 'ইউটিউব লিংক',
      'input.placeholder': 'https://www.youtube.com/watch?v=...',
      'input.getInfo': 'তথ্য আনুন',
      'input.hint': 'ভিডিও, শর্টস, লাইভ রিপ্লে ও প্লেলিস্ট সাপোর্ট করে। একাধিক লিংক হলে প্রতি লাইনে একটি দিন।',

      'batch.hint': 'নিচের সেটিংস দিয়ে সব লিংক কিউতে যোগ হবে।',
      'batch.preset': 'সব লিংকের কোয়ালিটি',
      'batch.count': '{n}টি লিংক পাওয়া গেছে',
      'batch.added': '{n}টি লিংক কিউতে যোগ হয়েছে',

      'btn.download': 'ডাউনলোড',
      'btn.selectAll': 'সব নির্বাচন',
      'btn.selectNone': 'নির্বাচন বাতিল',
      'btn.saveThumbnail': 'থাম্বনেইল সেভ',
      'btn.openYouTube': 'ইউটিউবে খুলুন',
      'btn.showAdvanced': 'অ্যাডভান্সড অপশন',
      'btn.addToQueue': '{n}টি লিংক কিউতে যোগ করুন',
      'btn.downloadSelected': 'নির্বাচিত ডাউনলোড ({n})',
      'btn.cancel': 'বাতিল',
      'btn.remove': 'মুছুন',
      'btn.retry': 'আবার চেষ্টা',
      'btn.saveFile': 'ফাইল সেভ করুন',
      'btn.downloadAgain': 'আবার ডাউনলোড',
      'btn.clear': 'পরিষ্কার',

      'section.options': 'কী ডাউনলোড করবেন বেছে নিন',
      'section.queue': 'ডাউনলোড কিউ',
      'section.history': 'ডাউনলোড হিস্ট্রি',
      'section.subtitles': 'সাবটাইটেল',
      'section.trim': 'ট্রিম / কাট',
      'section.format': 'নির্দিষ্ট ফরম্যাট',
      'section.filename': 'ফাইলের নাম (ঐচ্ছিক)',
      'section.playlist': 'প্লেলিস্ট',

      'preset.best': 'সেরা কোয়ালিটি',
      'preset.best.desc': 'সর্বোচ্চ ভিডিও + অডিও',
      'preset.mp4': 'MP4 (H.264)',
      'preset.mp4.desc': 'সব ডিভাইসে চলে',
      'preset.video.desc': 'ভিডিও + অডিও',
      'preset.audioMp3': 'MP3 অডিও',
      'preset.audioMp3.desc': '১৯২ kbps · MP3',
      'preset.audioM4a': 'M4A অডিও',
      'preset.audioM4a.desc': 'অরিজিনাল AAC',
      'preset.subtitles': 'শুধু সাবটাইটেল',
      'preset.subtitles.desc': 'SRT / VTT ফাইল',
      'preset.custom': 'কাস্টম ফরম্যাট',
      'preset.custom.desc': 'লিস্ট থেকে বেছে নিন',
      'preset.audio.desc': '{format} · {quality} kbps',

      'opt.audioFormat': 'অডিও ফরম্যাট',
      'opt.audioQuality': 'অডিও কোয়ালিটি',
      'opt.noConvert': 'অরিজিনাল (কনভার্ট নয়)',
      'opt.subtitleFormat': 'সাবটাইটেল ফরম্যাট',
      'opt.subtitleLang': 'সাবটাইটেল ভাষা',
      'opt.subsNone': 'সাবটাইটেল নেই',
      'opt.embedSubs': 'সাবটাইটেল ভিডিওর ভেতরে যুক্ত করুন',
      'opt.noSubs': 'এই ভিডিওতে কোনো সাবটাইটেল নেই।',
      'opt.noFormats': 'এই ভিডিওর জন্য কোনো ডাউনলোডযোগ্য ফরম্যাট পাওয়া যায়নি।',
      'opt.playlistQuality': 'সবার জন্য কোয়ালিটি',
      'opt.trimStart': 'শুরুর সময়',
      'opt.trimEnd': 'শেষের সময়',
      'opt.trimHint': 'উদাহরণ: 1:30 বা 90 (সেকেন্ড)। পুরো ভিডিওর জন্য খালি রাখুন।',
      'opt.filenamePlaceholder': 'নিজের ফাইলের নাম',
      'opt.ffmpegMissing': 'সার্ভারে ffmpeg নেই, তাই MP3 কনভার্সন, ট্রিম ও ফরম্যাট মার্জ করা যাবে না।',

      'status.queued': 'কিউতে আছে',
      'status.preparing': 'প্রস্তুত হচ্ছে',
      'status.downloading': 'ডাউনলোড হচ্ছে',
      'status.processing': 'প্রসেস হচ্ছে',
      'status.completed': 'সেভ করার জন্য প্রস্তুত',
      'status.failed': 'ব্যর্থ',
      'status.canceled': 'বাতিল',

      'queue.empty': 'এখনো কোনো ডাউনলোড নেই। উপরে লিংক পেস্ট করুন।',
      'queue.clearFinished': 'শেষ হওয়া সরান',
      'queue.eta': 'বাকি সময়',
      'queue.entry': '{i}/{n}',
      'queue.files': '{n}টি ফাইল',
      'queue.speed': 'গতি',

      'history.empty': 'এখনো কিছু নেই।',
      'history.clear': 'হিস্ট্রি মুছুন',
      'history.confirmClear': 'পুরো ডাউনলোড হিস্ট্রি মুছে ফেলবেন?',
      'history.expired': '{time} পরে সার্ভার থেকে ফাইলগুলো মুছে যায়।',
      'history.removed': 'হিস্ট্রি থেকে সরানো হয়েছে',

      'playlist.selected': '{n}টি নির্বাচিত',
      'playlist.truncated': 'শুধু প্রথম {n}টি ভিডিও দেখানো যাচ্ছে।',
      'playlist.empty': 'এই প্লেলিস্টে ডাউনলোড করার মতো ভিডিও নেই।',

      'mode.video': 'ভিডিও',
      'mode.audio': 'অডিও',
      'mode.subtitles': 'সাবটাইটেল',

      'toast.downloadStarted': 'ডাউনলোড কিউতে যোগ হয়েছে',
      'toast.completed': 'সেভের জন্য প্রস্তুত: {name}',
      'toast.failed': 'ডাউনলোড ব্যর্থ: {message}',
      'toast.canceled': 'ডাউনলোড বাতিল হয়েছে',
      'toast.queued': 'কিউতে যোগ হয়েছে',
      'toast.thumbnailSaved': 'থাম্বনেইল সেভ হয়েছে',
      'toast.offline': 'আপনি অফলাইনে আছেন। নতুন ডাউনলোড কাজ করবে না।',

      'err.emptyUrl': 'আগে একটি ইউটিউব লিংক পেস্ট করুন।',
      'err.invalid_trim': 'ট্রিমের সময় ঠিক আছে কিনা দেখুন (উদাহরণ: 1:30)।',
      'err.noSubtitleSelected': 'অন্তত একটি সাবটাইটেল ভাষা বেছে নিন।',
      'err.invalid_url': 'সঠিক ইউটিউব লিংক পেস্ট করুন।',
      'err.invalid_request': 'কিছু অপশন সঠিক নয়। একবার দেখে নিন।',
      'err.ffmpeg_missing': 'এই ফিচারের জন্য সার্ভারে ffmpeg দরকার।',
      'err.private_video': 'এই ভিডিওটি প্রাইভেট বা সাইন-ইন প্রয়োজন।',
      'err.age_restricted': 'বয়স-সীমাবদ্ধ ভিডিও ডাউনলোড করা যাবে না।',
      'err.unavailable': 'ভিডিওটি পাওয়া যাচ্ছে না বা সরিয়ে ফেলা হয়েছে।',
      'err.network': 'ইউটিউবে পৌঁছানো যাচ্ছে না। ইন্টারনেট সংযোগ দেখুন।',
      'err.extract_failed': 'ভিডিওর তথ্য পাওয়া যায়নি। এটি সীমাবদ্ধ হতে পারে।',
      'err.format_unavailable': 'এই ভিডিওতে ওই কোয়ালিটি নেই।',
      'err.no_file': 'ডাউনলোড শেষ কিন্তু কোনো ফাইল তৈরি হয়নি।',
      'err.queue_full': 'কিউ ভরে গেছে। শেষ হওয়ার জন্য অপেক্ষা করুন।',
      'err.rate_limited': 'অনেক বেশি অনুরোধ। একটু পরে চেষ্টা করুন।',
      'err.job_not_found': 'এই ডাউনলোড আর পাওয়া যাচ্ছে না।',
      'err.job_not_ready': 'ডাউনলোড এখনো চলছে।',
      'err.file_expired': 'ফাইলটির সময় শেষ। আবার ডাউনলোড করুন।',
      'err.no_subtitles': 'কোনো সাবটাইটেল ভাষা নির্বাচন করা হয়নি।',
      'err.thumbnail_failed': 'থাম্বনেইল আনা যায়নি।',
      'err.download_failed': 'ডাউনলোড ব্যর্থ হয়েছে। আবার চেষ্টা করুন।',
      'err.http_error': 'অনুরোধ ব্যর্থ হয়েছে। আবার চেষ্টা করুন।',
      'err.unknown': 'কিছু একটা সমস্যা হয়েছে। আবার চেষ্টা করুন।',

      'aria.theme': 'ডার্ক / লাইট মোড বদলান',
      'aria.language': 'ভাষা পরিবর্তন',
      'footer.disclaimer': 'শুধু ব্যক্তিগত ও শিক্ষামূলক ব্যবহারের জন্য। কপিরাইট ও ইউটিউবের শর্তাবলি মানুন।',
      'footer.builtWith': 'FastAPI + yt-dlp দিয়ে তৈরি',
    },
  };

  /* --------------------------------------------------------------- helpers */
  const $ = (id) => document.getElementById(id);
  const store = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
      } catch (_) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch (_) {}
    },
  };

  const escapeHtml = (value = '') =>
    String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

  const state = {
    lang: 'en',
    theme: 'dark',
    config: null,
    info: null,
    preset: 'best',
    presetIds: [],
    formatId: null,
    subtitleLangs: new Set(),
    playlistSelected: new Set(),
    playlistInfo: null,
    batchUrls: [],
    jobs: [],
    jobIndex: new Map(),
    initialized: false,
    autoDownloadId: null,
    inlineJobId: null,
    pollTimer: null,
    history: [],
    online: navigator.onLine,
  };

  const el = {};

  function cacheElements() {
    [
      'urlInput', 'fetchBtn', 'fetchBtnLabel', 'fetchSpinner', 'errorBox', 'errorText', 'errorClose',
      'demoBanner', 'batchSection', 'batchCount', 'batchList', 'batchBtn', 'batchBtnLabel', 'batchPreset',
      'videoSection', 'thumb', 'thumbDuration', 'videoTitle', 'metaUploader', 'metaViews', 'metaDuration',
      'metaDate', 'videoDesc', 'saveThumbBtn', 'openOnYouTube', 'presets', 'advanced', 'formatList',
      'audioFormat', 'audioQuality', 'audioOptions', 'subtitleChips', 'noSubsNote', 'subtitleFormat',
      'embedSubs', 'embedWrap', 'trimStart', 'trimEnd', 'filenameInput', 'ffmpegNote',
      'downloadBtn', 'downloadBtnLabel', 'downloadSpinner', 'inlineProgress', 'inlineProgressBar',
      'inlineProgressFill', 'inlineProgressNote',
      'playlistSection', 'playlistTitle', 'playlistCount', 'playlistList', 'playlistHint',
      'selectAllBtn', 'selectNoneBtn', 'playlistDownloadBtn', 'playlistDownloadLabel',
      'playlistQuality', 'playlistSubtitle', 'playlistFilename',
      'queueList', 'queueEmpty', 'queueCount', 'clearFinishedBtn',
      'historyList', 'historyEmpty', 'historyHint', 'clearHistoryBtn',
      'themeToggle', 'themeIcon', 'toasts', 'versionText',
    ].forEach((id) => {
      el[id] = $(id);
    });
  }

  function t(key, vars) {
    const dict = I18N[state.lang] || I18N.en;
    let text = dict[key];
    if (text === undefined) text = I18N.en[key];
    if (text === undefined) return key;
    if (vars) {
      Object.keys(vars).forEach((name) => {
        text = text.split(`{${name}}`).join(String(vars[name]));
      });
    }
    return text;
  }

  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll('[data-i18n]').forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((node) => {
      node.placeholder = t(node.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-aria]').forEach((node) => {
      node.setAttribute('aria-label', t(node.dataset.i18nAria));
    });
    document.querySelectorAll('[data-lang]').forEach((node) => {
      node.setAttribute('aria-pressed', String(node.dataset.lang === state.lang));
    });
  }

  const numFmt = () => new Intl.NumberFormat(state.lang === 'bn' ? 'bn-IN' : 'en-US');
  const relFmt = () => new Intl.RelativeTimeFormat(state.lang === 'bn' ? 'bn' : 'en', { numeric: 'auto' });

  function relTime(timestamp) {
    const diffMinutes = Math.round((timestamp - Date.now()) / 60000);
    if (Math.abs(diffMinutes) < 60) return relFmt().format(diffMinutes, 'minute');
    const hours = Math.round(diffMinutes / 60);
    if (Math.abs(hours) < 24) return relFmt().format(hours, 'hour');
    return relFmt().format(Math.round(hours / 24), 'day');
  }

  function fmtBytes(bytes) {
    const value = Number(bytes || 0);
    if (!value) return '—';
    const units = ['B', 'KB', 'MB', 'GB'];
    let index = 0;
    let size = value;
    while (size >= 1024 && index < units.length - 1) {
      size /= 1024;
      index += 1;
    }
    return `${size.toFixed(size < 10 && index > 0 ? 1 : 0)} ${units[index]}`;
  }

  function fmtDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    const pad = (value) => String(value).padStart(2, '0');
    return hours ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`;
  }

  function parseTime(value) {
    const text = String(value || '').trim();
    if (!text) return null;
    if (/^\d+(\.\d+)?$/.test(text)) return Number(text);
    const parts = text.split(':').map((part) => Number(part));
    if (parts.some((part) => Number.isNaN(part))) return null;
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return null;
  }

  /* ------------------------------------------------------------------ api */
  async function api(path, options = {}) {
    const init = { method: options.method || 'GET', headers: {} };
    if (options.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(path, init);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json().catch(() => null) : null;
    if (!response.ok) {
      const error = new Error((data && data.detail) || `HTTP ${response.status}`);
      error.code = (data && data.code) || 'http_error';
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function errorMessage(error) {
    if (!error) return t('err.unknown');
    const key = `err.${error.code}`;
    const dict = I18N[state.lang] || {};
    if (dict[key]) return dict[key];
    if (I18N.en[key]) return t(key);
    return error.message || t('err.unknown');
  }

  function toast(message, type = 'info', duration = 4500) {
    const node = document.createElement('div');
    node.className = `toast ${type}`;
    const icon = type === 'error' ? 'i-alert' : type === 'success' ? 'i-check' : 'i-sparkle';
    node.innerHTML = `<svg class="icon"><use href="#${icon}"/></svg><div class="toast-body"></div>`;
    node.querySelector('.toast-body').textContent = message;
    el.toasts.appendChild(node);
    window.setTimeout(() => {
      node.classList.add('leaving');
      window.setTimeout(() => node.remove(), 220);
    }, duration);
  }

  function showError(message) {
    el.errorText.textContent = message;
    el.errorBox.classList.remove('hidden');
  }

  function hideError() {
    el.errorBox.classList.add('hidden');
  }

  function savePrefs() {
    store.set('ytd.prefs', {
      preset: state.preset,
      audioFormat: el.audioFormat.value,
      audioQuality: el.audioQuality.value,
      subtitleFormat: el.subtitleFormat.value,
      embed: el.embedSubs.checked,
      subtitleLangs: [...state.subtitleLangs],
      batchPreset: el.batchPreset.value,
      playlistQuality: el.playlistQuality.value,
    });
  }

  function loadPrefs() {
    const prefs = store.get('ytd.prefs', {}) || {};
    if (prefs.audioFormat) el.audioFormat.value = prefs.audioFormat;
    if (prefs.audioQuality) el.audioQuality.value = prefs.audioQuality;
    if (prefs.subtitleFormat) el.subtitleFormat.value = prefs.subtitleFormat;
    if (typeof prefs.embed === 'boolean') el.embedSubs.checked = prefs.embed;
    if (prefs.batchPreset) el.batchPreset.value = prefs.batchPreset;
    if (prefs.playlistQuality) el.playlistQuality.value = prefs.playlistQuality;
    return prefs;
  }

  /* ---------------------------------------------------------------- theme */
  function setTheme(theme) {
    state.theme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = state.theme;
    try {
      localStorage.setItem('ytd.theme', state.theme);
    } catch (_) {}
    el.themeIcon.querySelector('use').setAttribute('href', state.theme === 'dark' ? '#i-sun' : '#i-moon');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', state.theme === 'dark' ? '#0b1120' : '#f4f6fb');
  }

  function setLang(lang) {
    state.lang = lang === 'bn' ? 'bn' : 'en';
    try {
      localStorage.setItem('ytd.lang', state.lang);
    } catch (_) {}
    applyI18n();
    if (state.info && state.info.type === 'video') {
      renderPresets();
      renderFormats();
      renderSubtitleChips();
    } else if (state.info && state.info.type === 'playlist') {
      renderPlaylist(state.info);
    }
    if (state.batchUrls.length) renderBatch(state.batchUrls);
    renderQueue();
    renderHistory();
    renderHistoryHint();
    renderInlineProgress();
  }

  /* ------------------------------------------------------------ url input */
  function parseUrls(text) {
    const raw = String(text || '');
    let urls = raw.match(/https?:\/\/[^\s"'<>]+/g) || [];
    if (!urls.length) {
      urls = raw
        .split(/[\s,]+/)
        .filter((part) => /youtu\.?be/i.test(part))
        .map((part) => `https://${part.replace(/^https?:\/\//, '')}`);
    }
    const cleaned = urls.map((url) => url.replace(/[),.;]+$/, '')).filter(Boolean);
    return [...new Set(cleaned)];
  }

  function setFetching(isLoading) {
    el.fetchBtn.disabled = isLoading;
    el.fetchBtnLabel.classList.toggle('hidden', isLoading);
    el.fetchSpinner.classList.toggle('hidden', !isLoading);
  }

  async function onFetch() {
    hideError();
    const urls = parseUrls(el.urlInput.value);
    if (!urls.length) {
      showError(t('err.emptyUrl'));
      return;
    }
    if (urls.length > 1) {
      el.videoSection.classList.add('hidden');
      el.playlistSection.classList.add('hidden');
      state.info = null;
      renderBatch(urls);
      return;
    }

    el.batchSection.classList.add('hidden');
    state.batchUrls = [];
    setFetching(true);
    try {
      const info = await api('/api/info', { method: 'POST', body: { url: urls[0] } });
      state.info = info;
      if (info.type === 'playlist') {
        el.videoSection.classList.add('hidden');
        renderPlaylist(info);
      } else {
        el.playlistSection.classList.add('hidden');
        renderVideo(info);
      }
    } catch (error) {
      el.videoSection.classList.add('hidden');
      el.playlistSection.classList.add('hidden');
      state.info = null;
      showError(errorMessage(error));
    } finally {
      setFetching(false);
    }
  }

  /* --------------------------------------------------------------- batch */
  function renderBatch(urls) {
    state.batchUrls = urls;
    el.batchSection.classList.remove('hidden');
    el.batchCount.textContent = t('batch.count', { n: urls.length });
    el.batchBtnLabel.textContent = t('btn.addToQueue', { n: urls.length });
    el.batchList.innerHTML = urls
      .map(
        (url, index) =>
          `<div class="batch-row"><span class="idx">${index + 1}</span><span class="truncate">${escapeHtml(url)}</span></div>`
      )
      .join('');
  }

  function presetValueToOptions(value) {
    if (value === 'audio_mp3') return { mode: 'audio', audio_format: 'mp3' };
    if (value === 'audio_m4a') return { mode: 'audio', audio_format: 'm4a' };
    if (value === 'best_mp4') return { mode: 'video', quality: 'best_mp4' };
    if (/^\d+$/.test(value)) return { mode: 'video', quality: value };
    return { mode: 'video', quality: 'best' };
  }

  async function onBatchQueue() {
    if (!state.batchUrls.length) return;
    el.batchBtn.disabled = true;
    try {
      const options = presetValueToOptions(el.batchPreset.value);
      const result = await api('/api/jobs/batch', {
        method: 'POST',
        body: { ...options, urls: state.batchUrls },
      });
      toast(t('batch.added', { n: result.count }), 'success');
      state.inlineJobId = null;
      savePrefs();
      startPolling();
      await pollJobs();
    } catch (error) {
      showError(errorMessage(error));
      toast(errorMessage(error), 'error');
    } finally {
      el.batchBtn.disabled = false;
    }
  }

  /* ---------------------------------------------------------------- video */
  function renderVideo(info) {
    state.formatId = null;
    el.videoSection.classList.remove('hidden');
    el.thumb.src = info.thumbnail || '';
    el.thumb.alt = info.title || '';
    el.thumbDuration.textContent = info.duration_str || '';
    el.thumbDuration.classList.toggle('hidden', !info.duration_str);
    el.videoTitle.textContent = info.title || '';

    const setMeta = (node, value) => {
      const span = node.querySelector('span');
      if (span) span.textContent = value || '';
      node.classList.toggle('hidden', !value);
    };
    setMeta(el.metaUploader, info.uploader || '');
    setMeta(el.metaViews, info.view_count ? `${numFmt().format(info.view_count)} ${state.lang === 'bn' ? 'ভিউ' : 'views'}` : '');
    setMeta(el.metaDuration, info.duration_str || '');
    setMeta(el.metaDate, info.upload_date ? formatUploadDate(info.upload_date) : '');
    el.videoDesc.textContent = info.description || '';
    el.videoDesc.classList.toggle('hidden', !info.description);

    if (info.url) {
      el.openOnYouTube.href = info.url;
      el.openOnYouTube.classList.remove('hidden');
    }

    el.filenameInput.value = '';
    el.trimStart.value = '';
    el.trimEnd.value = '';
    el.embedSubs.checked = false;

    const prefs = loadPrefs();
    state.subtitleLangs = new Set(
      (prefs.subtitleLangs || []).filter((code) => (info.subtitles || []).some((item) => item.code === code))
    );

    renderPresets();
    if (state.preset === 'custom' && !state.formatId && (info.formats || []).length) {
      state.formatId = info.formats[0].format_id;
    }
    renderFormats();
    renderSubtitleChips();
    updateOptionVisibility();
  }

  function formatUploadDate(value) {
    const text = String(value);
    if (text.length !== 8) return text;
    return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`;
  }

  function availablePresets() {
    const info = state.info || {};
    const heights = (info.available_qualities || []).filter((height) => height >= 144).slice(0, 4);
    const hasFfmpeg = !state.config || state.config.ffmpeg_available;
    const presets = [
      { id: 'best', icon: 'i-sparkle', title: t('preset.best'), desc: t('preset.best.desc') },
      { id: 'best_mp4', icon: 'i-film', title: t('preset.mp4'), desc: t('preset.mp4.desc') },
    ];
    heights.forEach((height) => {
      presets.push({ id: String(height), icon: 'i-film', title: `${height}p`, desc: t('preset.video.desc') });
    });
    if (hasFfmpeg) {
      presets.push(
        { id: 'audio_mp3', icon: 'i-music', title: t('preset.audioMp3'), desc: t('preset.audioMp3.desc') },
        { id: 'audio_m4a', icon: 'i-music', title: t('preset.audioM4a'), desc: t('preset.audioM4a.desc') }
      );
    }
    if ((info.subtitles || []).length) {
      presets.push({ id: 'subtitles', icon: 'i-subtitle', title: t('preset.subtitles'), desc: t('preset.subtitles.desc') });
    }
    presets.push({ id: 'custom', icon: 'i-file', title: t('preset.custom'), desc: t('preset.custom.desc') });
    return presets;
  }

  function renderPresets() {
    const presets = availablePresets();
    state.presetIds = presets.map((preset) => preset.id);
    const prefs = store.get('ytd.prefs', {}) || {};
    const audioAvailable = state.presetIds.includes('audio_mp3');
    const presetValid =
      state.presetIds.includes(state.preset) || (state.preset === 'audio_custom' && audioAvailable);
    if (!presetValid) {
      const preferred = prefs.preset;
      state.preset = preferred && state.presetIds.includes(preferred) ? preferred : 'best';
    }
    el.presets.innerHTML = '';
    presets.forEach((preset) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'preset';
      button.dataset.preset = preset.id;
      button.setAttribute('aria-pressed', String(preset.id === state.preset));
      button.innerHTML = `
        <span class="preset-top">
          <svg class="icon"><use href="#${preset.icon}"/></svg>
          <span class="preset-title"></span>
        </span>
        <span class="preset-desc"></span>
        <svg class="icon preset-check"><use href="#i-check"/></svg>`;
      button.querySelector('.preset-title').textContent = preset.title;
      button.querySelector('.preset-desc').textContent = preset.desc;
      button.addEventListener('click', () => selectPreset(preset.id));
      el.presets.appendChild(button);
    });
    updateDownloadState();
  }

  function selectPreset(presetId) {
    state.preset = presetId;
    if (presetId === 'audio_mp3') {
      el.audioFormat.value = 'mp3';
    } else if (presetId === 'audio_m4a') {
      el.audioFormat.value = 'm4a';
    }
    if (presetId === 'custom' && !state.formatId) {
      const first = (state.info?.formats || [])[0];
      if (first) state.formatId = first.format_id;
      renderFormats();
    }
    if (presetId === 'subtitles' && !state.subtitleLangs.size && (state.info?.subtitles || []).length) {
      const first = state.info.subtitles[0];
      state.subtitleLangs.add(first.code);
      renderSubtitleChips();
    }
    document.querySelectorAll('.preset').forEach((node) => {
      node.setAttribute('aria-pressed', String(node.dataset.preset === presetId));
    });
    updateOptionVisibility();
    updateDownloadState();
    savePrefs();
  }

  function renderFormats() {
    const formats = state.info?.formats || [];
    el.formatList.innerHTML = '';
    if (!formats.length) {
      el.formatList.innerHTML = `<p class="hint">${escapeHtml(t('opt.noFormats'))}</p>`;
      return;
    }
    formats.forEach((format) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'format-row';
      row.dataset.formatId = format.format_id;
      row.setAttribute('aria-pressed', String(state.formatId === format.format_id));
      const bits = [
        String(format.ext || '').toUpperCase(),
        format.fps ? `${format.fps}fps` : '',
        format.dynamic_range && format.dynamic_range !== 'SDR' ? format.dynamic_range : '',
        format.format_note || '',
      ].filter(Boolean);
      row.innerHTML = `
        <span class="fmt-main">${escapeHtml(format.label || format.resolution || '')}</span>
        <span class="fmt-sub">${escapeHtml(bits.join(' · '))}</span>
        <span class="tag ${format.is_audio ? 'audio' : 'video'}">${format.is_audio ? 'AUDIO' : 'VIDEO'}</span>
        <span class="fmt-sub" style="flex:0 0 auto">${escapeHtml(format.filesize_str || '')}</span>`;
      row.addEventListener('click', () => {
        state.formatId = format.format_id;
        selectPreset('custom');
        renderFormats();
      });
      el.formatList.appendChild(row);
    });
  }

  function renderSubtitleChips() {
    const subtitles = state.info?.subtitles || [];
    el.subtitleChips.innerHTML = '';
    el.noSubsNote.classList.toggle('hidden', subtitles.length > 0);
    subtitles.forEach((subtitle) => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.setAttribute('aria-pressed', String(state.subtitleLangs.has(subtitle.code)));
      chip.innerHTML = `${escapeHtml(subtitle.name)}${subtitle.auto ? '<span class="dot" title="auto-generated"></span>' : ''}`;
      chip.addEventListener('click', () => {
        if (state.subtitleLangs.has(subtitle.code)) state.subtitleLangs.delete(subtitle.code);
        else state.subtitleLangs.add(subtitle.code);
        chip.setAttribute('aria-pressed', String(state.subtitleLangs.has(subtitle.code)));
        updateOptionVisibility();
        savePrefs();
      });
      el.subtitleChips.appendChild(chip);
    });
  }

  function currentAudioPreset() {
    return state.preset === 'audio_mp3' || state.preset === 'audio_m4a' || state.preset === 'audio_custom';
  }

  function updateOptionVisibility() {
    const isAudio = currentAudioPreset();
    const isSubtitles = state.preset === 'subtitles';
    el.audioOptions.classList.toggle('hidden', !isAudio);
    const ffmpeg = !state.config || state.config.ffmpeg_available;
    const canEmbed = ffmpeg && !isAudio && !isSubtitles && state.subtitleLangs.size > 0;
    el.embedWrap.classList.toggle('hidden', !canEmbed);
    el.trimStart.disabled = !ffmpeg || isSubtitles;
    el.trimEnd.disabled = !ffmpeg || isSubtitles;
    el.audioFormat.disabled = false;
    updateDownloadState();
  }

  function updateDownloadState() {
    if (!el.downloadBtn) return;
    const preset = state.preset;
    const needsFormat = preset === 'custom' && !state.formatId;
    el.downloadBtn.disabled = !state.info || !preset || needsFormat;
  }

  function buildOptions() {
    const options = {
      mode: 'video',
      quality: 'best',
      audio_format: el.audioFormat.value,
      audio_quality: Number(el.audioQuality.value) || 192,
      subtitle_langs: [...state.subtitleLangs],
      subtitle_format: el.subtitleFormat.value,
      embed_subtitles: el.embedSubs.checked,
      filename: el.filenameInput.value.trim() || null,
      trim_start: parseTime(el.trimStart.value),
      trim_end: parseTime(el.trimEnd.value),
      title: state.info?.title || null,
      thumbnail: state.info?.thumbnail || null,
    };

    if (state.preset === 'audio_mp3' || state.preset === 'audio_m4a' || state.preset === 'audio_custom') {
      options.mode = 'audio';
      options.audio_format = state.preset === 'audio_custom' ? el.audioFormat.value : state.preset === 'audio_mp3' ? 'mp3' : 'm4a';
      options.quality = 'best';
    } else if (state.preset === 'subtitles') {
      options.mode = 'subtitles';
      options.embed_subtitles = false;
    } else if (state.preset === 'custom') {
      options.mode = 'video';
      options.quality = 'custom';
      options.format_id = state.formatId;
    } else if (['best', 'best_mp4', 'worst'].includes(state.preset)) {
      options.quality = state.preset;
    } else if (/^\d+$/.test(state.preset)) {
      options.quality = state.preset;
    }

    if (options.mode === 'subtitles' && !options.subtitle_langs.length) {
      throw Object.assign(new Error('no subtitles'), { code: 'no_subtitle_selected' });
    }
    if ((el.trimStart.value.trim() && options.trim_start === null) || (el.trimEnd.value.trim() && options.trim_end === null)) {
      throw Object.assign(new Error('invalid trim'), { code: 'invalid_trim' });
    }
    if (options.mode === 'video' && (!options.embed_subtitles || !state.subtitleLangs.size)) {
      options.embed_subtitles = false;
    }
    return options;
  }

  async function onDownload() {
    if (!state.info) return;
    hideError();
    let options;
    try {
      options = buildOptions();
    } catch (error) {
      const message = error.code === 'invalid_trim' ? t('err.invalid_trim') : errorMessage(error);
      showError(message);
      return;
    }

    el.downloadBtn.disabled = true;
    el.downloadSpinner.classList.remove('hidden');
    try {
      const job = await api('/api/jobs', {
        method: 'POST',
        body: { ...options, url: state.info.url },
      });
      state.autoDownloadId = job.id;
      state.inlineJobId = job.id;
      savePrefs();
      toast(t('toast.downloadStarted'), 'info');
      await pollJobs();
    } catch (error) {
      showError(errorMessage(error));
      toast(errorMessage(error), 'error');
    } finally {
      el.downloadSpinner.classList.add('hidden');
      updateDownloadState();
    }
  }

  /* ------------------------------------------------------------- playlist */
  function renderPlaylist(info) {
    state.playlistInfo = info;
    el.playlistSection.classList.remove('hidden');
    el.playlistTitle.textContent = info.title || '';
    el.playlistCount.textContent = String(info.count || info.entries?.length || 0);

    const entries = info.entries || [];
    state.playlistSelected = new Set(entries.map((entry) => entry.index));
    el.playlistHint.textContent = info.truncated ? t('playlist.truncated', { n: info.max_entries }) : '';
    el.playlistHint.classList.toggle('hidden', !info.truncated);

    el.playlistList.innerHTML = '';
    if (!entries.length) {
      el.playlistList.innerHTML = `<p class="hint">${escapeHtml(t('playlist.empty'))}</p>`;
    }
    entries.forEach((entry) => {
      const row = document.createElement('div');
      row.className = 'playlist-row selected';
      row.innerHTML = `
        <span class="checkbox"><input type="checkbox" checked /></span>
        <span class="p-index">${entry.index}</span>
        <img loading="lazy" src="${escapeHtml(entry.thumbnail || '')}" alt="" />
        <span class="p-title">${escapeHtml(entry.title || '')}</span>
        <span class="p-duration">${escapeHtml(entry.duration_str || '')}</span>`;
      const checkbox = row.querySelector('input');
      row.addEventListener('click', () => {
        const selected = !state.playlistSelected.has(entry.index);
        checkbox.checked = selected;
        togglePlaylistEntry(entry.index, selected, row);
      });
      el.playlistList.appendChild(row);
    });
    updatePlaylistSelection();
  }

  function togglePlaylistEntry(index, selected, row) {
    if (selected) state.playlistSelected.add(index);
    else state.playlistSelected.delete(index);
    if (row) row.classList.toggle('selected', selected);
    updatePlaylistSelection();
  }

  function updatePlaylistSelection() {
    const count = state.playlistSelected.size;
    el.playlistDownloadLabel.textContent = t('btn.downloadSelected', { n: count });
    el.playlistDownloadBtn.disabled = count === 0;
  }

  function selectAllPlaylist(selected) {
    state.playlistSelected = selected
      ? new Set((state.playlistInfo?.entries || []).map((entry) => entry.index))
      : new Set();
    document.querySelectorAll('.playlist-row').forEach((row, index) => {
      const entry = (state.playlistInfo?.entries || [])[index];
      const checkbox = row.querySelector('input');
      const active = Boolean(entry && state.playlistSelected.has(entry.index));
      checkbox.checked = active;
      row.classList.toggle('selected', active);
    });
    updatePlaylistSelection();
  }

  function compressItems(indexes) {
    const sorted = [...indexes].sort((a, b) => a - b);
    const parts = [];
    let start = null;
    let previous = null;
    sorted.forEach((value) => {
      if (start === null) {
        start = value;
        previous = value;
        return;
      }
      if (value === previous + 1) {
        previous = value;
        return;
      }
      parts.push(start === previous ? `${start}` : `${start}-${previous}`);
      start = value;
      previous = value;
    });
    if (start !== null) parts.push(start === previous ? `${start}` : `${start}-${previous}`);
    return parts.join(',');
  }

  async function onPlaylistDownload() {
    if (!state.playlistInfo || !state.playlistSelected.size) return;
    hideError();
    const options = presetValueToOptions(el.playlistQuality.value);
    options.playlist = true;
    options.playlist_items = compressItems(state.playlistSelected);
    options.entry_count = state.playlistSelected.size;
    options.title = state.playlistInfo.title;
    options.thumbnail = state.playlistInfo.thumbnail;
    options.filename = el.playlistFilename.value.trim() || null;
    const subtitleLang = el.playlistSubtitle.value;
    if (subtitleLang) {
      options.subtitle_langs = [subtitleLang];
      options.subtitle_format = el.subtitleFormat.value;
      options.embed_subtitles = false;
    }

    el.playlistDownloadBtn.disabled = true;
    try {
      const job = await api('/api/jobs', {
        method: 'POST',
        body: { ...options, url: state.playlistInfo.url },
      });
      state.autoDownloadId = job.id;
      state.inlineJobId = null;
      savePrefs();
      toast(t('toast.downloadStarted'), 'info');
      await pollJobs();
    } catch (error) {
      showError(errorMessage(error));
      toast(errorMessage(error), 'error');
    } finally {
      updatePlaylistSelection();
    }
  }

  /* ------------------------------------------------------------------ jobs */
  function statusLabel(job) {
    if (job.status === 'queued') return t('status.queued');
    if (job.status === 'completed') return t('status.completed');
    if (job.status === 'failed') return t('status.failed');
    if (job.status === 'canceled') return t('status.canceled');
    const map = {
      preparing: 'status.preparing',
      downloading: 'status.downloading',
      processing: 'status.processing',
    };
    return t(map[job.stage] || 'status.downloading');
  }

  function badgeClass(job) {
    if (job.status === 'running') return 'running';
    return job.status;
  }

  function modeSummary(job) {
    const options = job.options || {};
    if (job.mode === 'audio') {
      const format = (options.audio_format || 'mp3').toUpperCase();
      const quality = options.audio_quality ? ` ${options.audio_quality}k` : '';
      return `${t('mode.audio')} · ${format}${quality}`;
    }
    if (job.mode === 'subtitles') {
      const langs = (options.subtitle_langs || []).join(', ').toUpperCase() || t('mode.subtitles');
      return `${t('mode.subtitles')} · ${langs}`;
    }
    const quality = options.quality;
    if (quality === 'best') return t('preset.best');
    if (quality === 'best_mp4') return 'MP4 (H.264)';
    if (quality === 'custom') return options.format_id ? `#${options.format_id}` : t('preset.custom');
    if (/^\d+$/.test(String(quality))) return `${quality}p`;
    return t('mode.video');
  }

  function progressNoteHtml(job) {
    const bits = [];
    if (job.status === 'running' && job.progress) bits.push(`<strong>${Math.round(job.progress)}%</strong>`);
    if (job.speed_str) bits.push(`<span>${escapeHtml(job.speed_str)}</span>`);
    if (job.eta_str) bits.push(`<span>${escapeHtml(t('queue.eta'))} ${escapeHtml(job.eta_str)}</span>`);
    if (job.total_bytes) {
      bits.push(`<span>${escapeHtml(fmtBytes(job.downloaded_bytes))} / ${escapeHtml(fmtBytes(job.total_bytes))}</span>`);
    }
    if (job.entry_count > 1) {
      bits.push(`<span>${escapeHtml(t('queue.entry', { i: job.entry_index || 1, n: job.entry_count }))}</span>`);
    }
    return bits.join('');
  }

  function jobTitle(job) {
    return job.title || job.options?.title || job.url || '—';
  }

  function jobThumb(job) {
    const thumb = job.thumbnail || job.options?.thumbnail;
    if (!thumb) return '';
    return `<img class="job-thumb" loading="lazy" src="${escapeHtml(thumb)}" alt="" onerror="this.style.display='none'" />`;
  }

  function renderQueue() {
    const jobs = state.jobs || [];
    el.queueList.innerHTML = '';
    el.queueEmpty.classList.toggle('hidden', jobs.length > 0);
    const activeCount = jobs.filter((job) => job.status === 'queued' || job.status === 'running').length;
    el.queueCount.textContent = String(jobs.length);
    el.queueCount.classList.toggle('hidden', jobs.length === 0);
    el.clearFinishedBtn.disabled = !jobs.some((job) => ['completed', 'failed', 'canceled'].includes(job.status));

    const active = jobs.filter((job) => job.status === 'queued' || job.status === 'running');
    const finished = jobs
      .filter((job) => !['queued', 'running'].includes(job.status))
      .sort((a, b) => (b.finished_at || 0) - (a.finished_at || 0));
    const ordered = [...active, ...finished].slice(0, 30);

    ordered.forEach((job) => {
      const node = document.createElement('div');
      node.className = `job ${job.status}`;
      node.dataset.jobId = job.id;

      const size = job.status === 'completed' ? job.result_size_str : job.total_str;
      const metaBits = [`<span class="badge ${badgeClass(job)}">${escapeHtml(statusLabel(job))}</span>`, `<span>${escapeHtml(modeSummary(job))}</span>`];
      if (size) metaBits.push(`<span>${escapeHtml(size)}</span>`);
      if (job.status === 'completed' && job.file_count > 1) {
        metaBits.push(`<span>${escapeHtml(t('queue.files', { n: job.file_count }))}</span>`);
      }

      const isActive = job.status === 'queued' || job.status === 'running';
      const progressBlock = isActive
        ? `<div class="progress ${job.progress ? '' : 'indeterminate'}"><div class="progress-fill" style="width:${Math.min(100, job.progress || 0)}%"></div></div>
           <div class="progress-note">${progressNoteHtml(job)}</div>`
        : '';
      const errorBlock = job.status === 'failed' ? `<div class="job-error">${escapeHtml(job.error || t('status.failed'))}</div>` : '';

      const actions = [];
      if (isActive) {
        actions.push(`<button type="button" class="btn btn-sm btn-ghost" data-action="cancel"><svg class="icon"><use href="#i-stop"/></svg><span>${escapeHtml(t('btn.cancel'))}</span></button>`);
      } else if (job.status === 'completed') {
        actions.push(`<a class="btn btn-sm btn-accent" data-action="save" href="${escapeHtml(job.download_url || `/api/jobs/${job.id}/file`)}" download="${escapeHtml(job.result_name || '')}"><svg class="icon"><use href="#i-download"/></svg><span>${escapeHtml(t('btn.saveFile'))}</span></a>`);
      } else {
        actions.push(`<button type="button" class="btn btn-sm btn-ghost" data-action="retry"><svg class="icon"><use href="#i-refresh"/></svg><span>${escapeHtml(t('btn.retry'))}</span></button>`);
      }
      actions.push(`<button type="button" class="btn btn-sm btn-danger" data-action="remove" title="${escapeHtml(t('btn.remove'))}"><svg class="icon"><use href="#i-trash"/></svg></button>`);

      node.innerHTML = `
        <div class="job-top">
          ${jobThumb(job)}
          <div class="job-info">
            <div class="job-title">${escapeHtml(jobTitle(job))}</div>
            <div class="job-sub">${metaBits.join('')}</div>
          </div>
        </div>
        ${progressBlock}
        ${errorBlock}
        <div class="job-actions">${actions.join('')}</div>`;

      node.querySelectorAll('[data-action]').forEach((button) => {
        button.addEventListener('click', () => {
          const action = button.dataset.action;
          if (action === 'cancel') cancelJob(job.id);
          else if (action === 'remove') removeJob(job.id);
          else if (action === 'retry') retryJob(job);
        });
      });
      node.querySelector('[data-action="save"]')?.addEventListener('click', () => {
        if (state.autoDownloadId === job.id) state.autoDownloadId = null;
      });

      el.queueList.appendChild(node);
    });
  }

  function renderInlineProgress() {
    const job = state.inlineJobId ? state.jobIndex.get(state.inlineJobId) : null;
    if (!job || ['completed', 'failed', 'canceled'].includes(job.status)) {
      el.inlineProgress.classList.add('hidden');
      return;
    }
    el.inlineProgress.classList.remove('hidden');
    const percent = Math.min(100, job.progress || 0);
    el.inlineProgressBar.classList.toggle('indeterminate', !job.progress);
    el.inlineProgressFill.style.width = `${percent}%`;
    el.inlineProgressNote.innerHTML = progressNoteHtml(job);
  }

  async function pollJobs() {
    let data;
    try {
      data = await api('/api/jobs');
    } catch (error) {
      state.online = navigator.onLine;
      schedulePoll(4000);
      return;
    }
    const jobs = data.jobs || [];
    const previous = state.jobIndex;
    const isFirstRun = !state.initialized;

    jobs.forEach((job) => {
      const old = previous.get(job.id);
      if (isFirstRun) return;
      if (job.status === 'completed' && (!old || old.status !== 'completed')) onJobCompleted(job);
      if (job.status === 'failed' && (!old || old.status !== 'failed')) {
        toast(t('toast.failed', { message: job.error || '' }), 'error', 7000);
      }
      if (job.status === 'canceled' && old && old.status !== 'canceled') {
        toast(t('toast.canceled'), 'warning');
      }
    });

    state.initialized = true;
    state.jobs = jobs;
    state.jobIndex = new Map(jobs.map((job) => [job.id, job]));
    renderQueue();
    renderInlineProgress();

    const active = jobs.some((job) => job.status === 'queued' || job.status === 'running');
    schedulePoll(active ? 900 : 6000);
  }

  function schedulePoll(delay) {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = window.setTimeout(() => {
      if (document.hidden) {
        schedulePoll(1500);
        return;
      }
      pollJobs();
    }, delay);
  }

  function startPolling() {
    schedulePoll(400);
  }

  function onJobCompleted(job) {
    addHistory(job);
    const name = job.result_name || job.title || '';
    toast(t('toast.completed', { name }), 'success', 6000);

    if (state.autoDownloadId === job.id) {
      state.autoDownloadId = null;
      const anchor = document.createElement('a');
      anchor.href = job.download_url || `/api/jobs/${job.id}/file`;
      anchor.download = job.result_name || '';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    }
  }

  async function cancelJob(jobId) {
    try {
      await api(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      await pollJobs();
    } catch (error) {
      toast(errorMessage(error), 'error');
    }
  }

  async function removeJob(jobId) {
    try {
      await api(`/api/jobs/${jobId}`, { method: 'DELETE' });
      state.jobIndex.delete(jobId);
      if (state.inlineJobId === jobId) state.inlineJobId = null;
      await pollJobs();
    } catch (error) {
      toast(errorMessage(error), 'error');
    }
  }

  async function retryJob(job) {
    try {
      const options = { ...(job.options || {}) };
      delete options.url;
      const created = await api('/api/jobs', {
        method: 'POST',
        body: { ...options, url: job.url, title: job.title, thumbnail: job.thumbnail },
      });
      state.autoDownloadId = created.id;
      state.inlineJobId = null;
      toast(t('toast.queued'), 'info');
      await pollJobs();
    } catch (error) {
      toast(errorMessage(error), 'error');
    }
  }

  async function clearFinished() {
    const finished = state.jobs.filter((job) => ['completed', 'failed', 'canceled'].includes(job.status));
    el.clearFinishedBtn.disabled = true;
    await Promise.all(
      finished.map((job) =>
        api(`/api/jobs/${job.id}`, { method: 'DELETE' }).catch(() => null)
      )
    );
    await pollJobs();
  }

  /* --------------------------------------------------------------- history */
  function loadHistory() {
    const list = store.get('ytd.history', []);
    state.history = Array.isArray(list) ? list : [];
  }

  function saveHistory() {
    store.set('ytd.history', state.history.slice(0, 60));
  }

  function addHistory(job) {
    const entry = {
      id: job.id,
      url: job.url,
      title: jobTitle(job),
      thumbnail: job.thumbnail || job.options?.thumbnail || null,
      mode: job.mode,
      size: job.result_size_str || null,
      files: job.file_count || 1,
      at: Date.now(),
      options: { ...(job.options || {}) },
    };
    state.history = [entry, ...state.history.filter((item) => item.id !== entry.id)].slice(0, 60);
    saveHistory();
    renderHistory();
    renderHistoryHint();
  }

  function renderHistory() {
    el.historyList.innerHTML = '';
    el.historyEmpty.classList.toggle('hidden', state.history.length > 0);
    state.history.forEach((entry) => {
      const node = document.createElement('div');
      node.className = 'history-item';
      const meta = [modeSummary({ mode: entry.mode, options: entry.options }), entry.size, relTime(entry.at)].filter(Boolean);
      node.innerHTML = `
        ${entry.thumbnail ? `<img loading="lazy" src="${escapeHtml(entry.thumbnail)}" alt="" onerror="this.style.display='none'" />` : ''}
        <div class="h-info">
          <div class="h-title">${escapeHtml(entry.title || entry.url)}</div>
          <div class="h-meta">${meta.map((bit) => `<span>${escapeHtml(bit)}</span>`).join('')}</div>
        </div>
        <button type="button" class="btn btn-sm btn-ghost" data-action="again" title="${escapeHtml(t('btn.downloadAgain'))}">
          <svg class="icon"><use href="#i-refresh"/></svg>
        </button>
        <button type="button" class="btn btn-sm btn-danger" data-action="forget" title="${escapeHtml(t('btn.remove'))}">
          <svg class="icon"><use href="#i-trash"/></svg>
        </button>`;
      node.querySelector('[data-action="again"]').addEventListener('click', () => redownload(entry));
      node.querySelector('[data-action="forget"]').addEventListener('click', () => {
        state.history = state.history.filter((item) => item.id !== entry.id);
        saveHistory();
        renderHistory();
        toast(t('history.removed'), 'info', 2500);
      });
      el.historyList.appendChild(node);
    });
  }

  function renderHistoryHint() {
    if (!state.config || !state.config.max_file_age_seconds) {
      el.historyHint.classList.add('hidden');
      return;
    }
    const seconds = state.config.max_file_age_seconds;
    const label = seconds >= 3600 ? `${Math.round(seconds / 3600)}h` : `${Math.round(seconds / 60)} min`;
    el.historyHint.textContent = t('history.expired', { time: label });
    el.historyHint.classList.remove('hidden');
  }

  async function redownload(entry) {
    try {
      const options = { ...(entry.options || {}) };
      delete options.url;
      const job = await api('/api/jobs', {
        method: 'POST',
        body: { ...options, url: entry.url, title: entry.title, thumbnail: entry.thumbnail },
      });
      state.autoDownloadId = job.id;
      state.inlineJobId = null;
      toast(t('toast.queued'), 'info');
      await pollJobs();
    } catch (error) {
      toast(errorMessage(error), 'error');
    }
  }

  function clearHistory() {
    if (!state.history.length) return;
    if (!window.confirm(t('history.confirmClear'))) return;
    state.history = [];
    saveHistory();
    renderHistory();
  }

  /* ------------------------------------------------------------- thumbnail */
  function saveThumbnail() {
    const info = state.info;
    if (!info || !info.thumbnail) return;
    const base = `${info.title || 'thumbnail'} [thumbnail]`;
    let href;
    if (info.thumbnail.startsWith('/')) {
      href = info.thumbnail;
    } else {
      href = `/api/thumbnail?url=${encodeURIComponent(info.thumbnail)}&name=${encodeURIComponent(base)}`;
    }
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = `${base}.jpg`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    toast(t('toast.thumbnailSaved'), 'success', 3000);
  }

  /* ------------------------------------------------------------------ pwa */
  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    const secure = window.isSecureContext || ['localhost', '127.0.0.1'].includes(location.hostname);
    if (!secure) return;
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  /* ----------------------------------------------------------------- init */
  function bindEvents() {
    el.fetchBtn.addEventListener('click', onFetch);
    el.errorClose.addEventListener('click', hideError);
    el.urlInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        onFetch();
      }
    });
    el.downloadBtn.addEventListener('click', onDownload);
    el.batchBtn.addEventListener('click', onBatchQueue);
    el.batchPreset.addEventListener('change', savePrefs);
    el.playlistDownloadBtn.addEventListener('click', onPlaylistDownload);
    el.selectAllBtn.addEventListener('click', () => selectAllPlaylist(true));
    el.selectNoneBtn.addEventListener('click', () => selectAllPlaylist(false));
    el.playlistQuality.addEventListener('change', savePrefs);
    el.playlistSubtitle.addEventListener('change', savePrefs);
    el.clearFinishedBtn.addEventListener('click', clearFinished);
    el.clearHistoryBtn.addEventListener('click', clearHistory);
    el.saveThumbBtn.addEventListener('click', saveThumbnail);
    el.audioFormat.addEventListener('change', () => {
      if (currentAudioPreset()) {
        state.preset = ['mp3', 'm4a'].includes(el.audioFormat.value) ? `audio_${el.audioFormat.value}` : 'audio_custom';
        document.querySelectorAll('.preset').forEach((node) => {
          node.setAttribute('aria-pressed', String(node.dataset.preset === state.preset));
        });
      }
      savePrefs();
      updateOptionVisibility();
    });
    el.audioQuality.addEventListener('change', savePrefs);
    el.subtitleFormat.addEventListener('change', savePrefs);
    el.embedSubs.addEventListener('change', savePrefs);
    el.themeToggle.addEventListener('click', () => setTheme(state.theme === 'dark' ? 'light' : 'dark'));
    document.querySelectorAll('[data-lang]').forEach((button) => {
      button.addEventListener('click', () => setLang(button.dataset.lang));
    });
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) pollJobs();
    });
    window.addEventListener('online', () => {
      state.online = true;
      pollJobs();
    });
    window.addEventListener('offline', () => {
      state.online = false;
      toast(t('toast.offline'), 'warning', 5000);
    });
  }

  async function init() {
    cacheElements();
    state.theme = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
    let savedLang = 'en';
    try {
      savedLang = localStorage.getItem('ytd.lang') || 'en';
    } catch (_) {}
    state.lang = savedLang === 'bn' ? 'bn' : 'en';

    setTheme(state.theme);
    applyI18n();
    loadPrefs();
    loadHistory();
    bindEvents();
    renderHistory();
    renderQueue();

    try {
      state.config = await api('/api/config');
    } catch (_) {
      state.config = null;
    }
    if (state.config) {
      el.demoBanner.classList.toggle('hidden', !state.config.demo_mode);
      if (!state.config.ffmpeg_available) {
        el.ffmpegNote.classList.remove('hidden');
        el.embedWrap.classList.add('hidden');
      }
      renderHistoryHint();
    }

    registerServiceWorker();
    await pollJobs();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
