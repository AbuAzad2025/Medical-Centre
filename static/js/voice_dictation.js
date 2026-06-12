/**
 * Voice Dictation using Web Speech API
 * Enable voice input on textarea elements with data-voice-dictation="true"
 */
(function() {
  'use strict';

  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    console.warn('Web Speech API not supported');
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function initVoiceDictation() {
    const textareas = document.querySelectorAll('[data-voice-dictation="true"], textarea[name*="notes"], textarea[name*="diagnosis"], textarea[name*="plan"]');
    textareas.forEach(function(textarea) {
      if (textarea.parentElement.querySelector('.voice-btn')) return;

      const wrapper = document.createElement('div');
      wrapper.className = 'position-relative';
      textarea.parentNode.insertBefore(wrapper, textarea);
      wrapper.appendChild(textarea);

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'voice-btn btn btn-sm btn-outline-secondary position-absolute';
      btn.style.top = '5px';
      btn.style.right = '5px';
      btn.style.zIndex = '10';
      btn.innerHTML = '<i class="bi bi-mic"></i>';
      btn.title = 'إملاء صوتي / Voice Dictation';
      wrapper.appendChild(btn);

      const lang = document.documentElement.lang || 'ar';
      let recognition = null;
      let isRecording = false;

      btn.addEventListener('click', function() {
        if (isRecording) {
          if (recognition) recognition.stop();
          isRecording = false;
          btn.innerHTML = '<i class="bi bi-mic"></i>';
          btn.classList.remove('btn-danger');
          btn.classList.add('btn-outline-secondary');
          return;
        }

        recognition = new SpeechRecognition();
        recognition.lang = lang === 'ar' ? 'ar-SA' : 'en-US';
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        recognition.onstart = function() {
          isRecording = true;
          btn.innerHTML = '<i class="bi bi-mic-fill"></i> <span class="recording-dot"></span>';
          btn.classList.remove('btn-outline-secondary');
          btn.classList.add('btn-danger');
          textarea.focus();
        };

        recognition.onresult = function(event) {
          let finalTranscript = '';
          let interimTranscript = '';
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript + ' ';
            } else {
              interimTranscript += transcript;
            }
          }
          if (finalTranscript) {
            const cursorPos = textarea.selectionStart;
            const text = textarea.value;
            textarea.value = text.slice(0, cursorPos) + finalTranscript + text.slice(cursorPos);
            textarea.selectionStart = cursorPos + finalTranscript.length;
            textarea.selectionEnd = cursorPos + finalTranscript.length;
          }
        };

        recognition.onerror = function(event) {
          console.error('Speech recognition error', event.error);
          isRecording = false;
          btn.innerHTML = '<i class="bi bi-mic"></i>';
          btn.classList.remove('btn-danger');
          btn.classList.add('btn-outline-secondary');
        };

        recognition.onend = function() {
          if (isRecording) {
            // Restart if still recording (browser may stop after pause)
            try { recognition.start(); } catch(e) {}
          }
        };

        recognition.start();
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoiceDictation);
  } else {
    initVoiceDictation();
  }
})();
