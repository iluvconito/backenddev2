document.addEventListener('DOMContentLoaded', () => {
  const catalogForm = document.querySelector('.catalog-tools');
  if (catalogForm) {
    const category = catalogForm.querySelector('select[name="categoria"]');
    const search = catalogForm.querySelector('input[name="q"]');
    const cards = [...document.querySelectorAll('.equipment-card')];
    const emptyState = document.querySelector('#catalog-empty');

    const filterEquipment = () => {
      const selectedCategory = category.value;
      const searchTerm = search.value.trim().toLocaleLowerCase('es');
      let visibleCount = 0;

      cards.forEach((card) => {
        const matchesCategory = !selectedCategory || card.dataset.category === selectedCategory;
        const matchesSearch = !searchTerm || card.dataset.search.toLocaleLowerCase('es').includes(searchTerm);
        card.hidden = !matchesCategory || !matchesSearch;
        if (!card.hidden) visibleCount += 1;
      });

      if (emptyState) emptyState.hidden = visibleCount > 0;
    };

    category.addEventListener('change', filterEquipment);
    search.addEventListener('input', filterEquipment);
    catalogForm.addEventListener('submit', (event) => {
      event.preventDefault();
      filterEquipment();
    });
  }

  const startDate = document.querySelector('input[name="start_date"]');
  const endDate = document.querySelector('input[name="end_date"]');
  if (!startDate || !endDate) return;

  const today = new Date();
  const localToday = new Date(today.getTime() - today.getTimezoneOffset() * 60000)
    .toISOString().slice(0, 10);
  startDate.min = localToday;
  endDate.min = localToday;
  startDate.addEventListener('change', () => {
    endDate.min = startDate.value || localToday;
    if (endDate.value && endDate.value < endDate.min) endDate.value = endDate.min;
  });
});
