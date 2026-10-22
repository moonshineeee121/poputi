document.querySelector('[data-menu-toggle]')?.addEventListener('click', (event) => {
  const button = event.currentTarget;
  const opened = button.getAttribute('aria-expanded') !== 'true';
  button.setAttribute('aria-expanded', String(opened));
  document.querySelector('.navigation').classList.toggle('is-open', opened);
});
document.querySelector('[data-filter-toggle]')?.addEventListener('click', (event) => {
  const opened = document.querySelector('[data-filters]').classList.toggle('is-open');
  event.currentTarget.setAttribute('aria-expanded', String(opened));
});
const bookingForm = document.querySelector('[data-booking-form]');
if (bookingForm) {
  const departure = bookingForm.querySelector('[data-departure]');
  const seats = bookingForm.querySelector('[data-seats]');
  const updateBooking = () => {
    const option = departure.selectedOptions[0];
    const free = Number(option.dataset.free);
    bookingForm.action = option.dataset.url;
    bookingForm.querySelector('[data-free-count]').textContent = free;
    seats.max = free;
    const total = Number(option.dataset.price) * (Number(seats.value) || 1);
    bookingForm.querySelector('[data-total]').textContent = new Intl.NumberFormat('ru-RU', {style: 'currency', currency: 'RUB', maximumFractionDigits: 0}).format(total);
    const submit = bookingForm.querySelector('button[type="submit"]');
    if (submit) {
      submit.disabled = free < 1;
      submit.innerHTML = free < 1 ? 'Все места заняты' : 'Забронировать <span aria-hidden="true">↗</span>';
    }
  };
  departure.addEventListener('change', updateBooking);
  seats.addEventListener('input', updateBooking);
  updateBooking();
}
document.querySelectorAll('[data-cancel-form]').forEach(form => form.addEventListener('submit', event => {
  if (!window.confirm('Отменить бронь? Ваши места снова станут доступны другим путешественникам.')) event.preventDefault();
}));
