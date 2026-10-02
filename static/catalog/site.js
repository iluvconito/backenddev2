/* Filtra tarjetas del catálogo y consulta por fechas la disponibilidad en sedes. */
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

  const inventoryBranch = document.querySelector('#inventory-branch-filter');
  const inventorySearch = document.querySelector('#inventory-equipment-filter');
  if (inventoryBranch && inventorySearch) {
    const inventoryRows = [...document.querySelectorAll('[data-inventory-row]')];
    const inventoryEmpty = document.querySelector('#inventory-filter-empty');
    const inventoryClear = document.querySelector('#inventory-filter-clear');

    const filterInventory = () => {
      const branchId = inventoryBranch.value;
      const searchTerm = inventorySearch.value.trim().toLocaleLowerCase('es');
      let visibleCount = 0;

      inventoryRows.forEach((row) => {
        const matchesBranch = Boolean(branchId) && row.dataset.branchId === branchId;
        const matchesName = !searchTerm
          || row.dataset.equipmentName.toLocaleLowerCase('es').includes(searchTerm);
        row.hidden = !matchesBranch || !matchesName;
        if (!row.hidden) visibleCount += 1;
      });

      if (inventoryEmpty) {
        inventoryEmpty.hidden = visibleCount > 0;
        inventoryEmpty.querySelector('td').textContent = branchId
          ? 'No hay maquinaria que coincida con los filtros seleccionados.'
          : 'Selecciona una sede para consultar su inventario.';
      }
    };

    inventoryBranch.addEventListener('change', filterInventory);
    inventorySearch.addEventListener('input', filterInventory);
    inventoryClear.addEventListener('click', () => {
      inventoryBranch.value = '';
      inventorySearch.value = '';
      filterInventory();
    });
    filterInventory();
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

  const availabilityPanel = document.querySelector('.stock-availability');
  if (!availabilityPanel) return;
  const availabilityList = availabilityPanel.querySelector('#stock-list');
  const availabilityTotal = availabilityPanel.querySelector('#stock-total');
  const availabilityStatus = availabilityPanel.querySelector('#stock-status');
  const branchSelect = document.querySelector('select[name="branch"]');
  let availabilityRequest;

  const refreshAvailability = async () => {
    if (!startDate.value || !endDate.value || endDate.value < startDate.value) return;

    if (availabilityRequest) availabilityRequest.abort();
    availabilityRequest = new AbortController();
    const url = new URL(availabilityPanel.dataset.availabilityUrl, window.location.href);
    url.searchParams.set('start_date', startDate.value);
    url.searchParams.set('end_date', endDate.value);

    try {
      const response = await fetch(url, { signal: availabilityRequest.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'No se pudo consultar la disponibilidad.');

      availabilityTotal.textContent = `${data.total} ${data.total === 1 ? 'unidad disponible' : 'unidades disponibles'}`;
      availabilityStatus.textContent = 'Disponibilidad para las fechas seleccionadas.';
      availabilityList.replaceChildren(...data.branches.map((branch) => {
        const item = document.createElement('li');
        item.dataset.branchId = branch.id;
        item.dataset.quantity = branch.quantity;

        const location = document.createElement('span');
        const name = document.createElement('strong');
        name.textContent = branch.name;
        const address = document.createElement('small');
        address.textContent = `${branch.region} · ${branch.address}`;
        location.append(name, address);

        const quantity = document.createElement('b');
        quantity.textContent = branch.quantity
          ? `${branch.quantity} disponible${branch.quantity === 1 ? '' : 's'}`
          : 'Sin disponibilidad';
        item.append(location, quantity);
        return item;
      }));

      if (branchSelect) {
        [...branchSelect.options].forEach((option) => {
          if (!option.value) return;
          const selectedBranch = data.branches.find((branch) => String(branch.id) === option.value);
          option.disabled = !selectedBranch || selectedBranch.quantity < 1;
        });
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        availabilityStatus.textContent = error.message;
      }
    }
  };

  startDate.addEventListener('change', refreshAvailability);
  endDate.addEventListener('change', refreshAvailability);
  refreshAvailability();
});
