/**
 * Internationalization (i18n) loader and text updater for EN / TH
 */

export let currentLang = "en";
let dictionary = {};

export async function setLanguage(lang) {
  try {
    const res = await fetch(`i18n/${lang}.json`);
    if (res.ok) {
      dictionary = await res.json();
      currentLang = lang;
      updateDomTexts();
    }
  } catch (e) {
    console.error("Failed to load language:", lang, e);
  }
}

export function t(key, defaultVal = "") {
  return dictionary[key] || defaultVal || key;
}

export function updateDomTexts() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dictionary[key]) {
      el.textContent = dictionary[key];
    }
  });

  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    const key = el.getAttribute("data-i18n-ph");
    if (dictionary[key]) {
      el.setAttribute("placeholder", dictionary[key]);
    }
  });
}
