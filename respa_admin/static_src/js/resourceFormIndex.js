import { initializeEventHandlers, initialSortPeriodDays, setClonableItems, calendarHandler, coloredDropdownListener, addDropdownColor }  from './resourceForm';
import { toggleCurrentLanguage, calculateTranslatedFields, getCurrentLanguage, toggleLanguage }  from './resourceFormLanguage';

function start() {
  initializeEventHandlers();
  setClonableItems();
  toggleCurrentLanguage();
  if (getCurrentLanguage() === 'fi') {
    toggleLanguage('sv');
  } else if (getCurrentLanguage() === 'sv') {
    toggleLanguage('fi');
  }
  calculateTranslatedFields();
  calendarHandler();
  initialSortPeriodDays();
  addDropdownColor();
  coloredDropdownListener();
}

window.addEventListener('load', start, false);
