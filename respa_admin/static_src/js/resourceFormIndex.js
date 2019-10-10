import { initializeEventHandlers, initialSortPeriodDays, setClonableItems, calendarHandler, coloredDropdownListener, addDropdownColor }  from './resourceForm';
import { toggleCurrentLanguage, calculateTranslatedFields, getCurrentLanguage, toggleLanguage }  from './resourceFormLanguage';

function start() {
  initializeResourceForm();
  toggleCurrentLanguage();
  if (getCurrentLanguage() === 'fi') {
    toggleLanguage('sv');
  } else if (getCurrentLanguage() === 'sv') {
    toggleLanguage('fi');
  }
  calculateTranslatedFields();
  calendarHandler();
  addDropdownColor();
  coloredDropdownListener();
}

window.addEventListener('load', start, false);
