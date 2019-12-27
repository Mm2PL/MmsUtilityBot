/**
 * @author Mm2PL & caglapickaxe
 * @license GNU General Public License
 */
(function suggestions() {
  let currentPage = -1;
  let isLoading = false;

  const loadingFailed = document.getElementById("loadingFailed");
  const loadingInfo = document.getElementById("loadingInfo");
  const buttonNext = document.getElementById("buttonNext");
  const buttonPrev = document.getElementById("buttonPrev");

  function updatePageNumber() {
    document.getElementById("pageNum").innerText = `Page ${currentPage}`;
    document.title = `Mm's bot (suggestions page ${currentPage})`;
  };

  function load(page) {
    history.pushState({ currentPage: page }, `Mm's bot (suggestions page ${page})`, `?page=${page}`);
    currentPage = page;
    isLoading = true;

    fetch(`https://kotmisia.pl/api/suggestions/list/${page}`)
      .then(res => res.json())
      .then(json => {
        updatePageNumber();

        const list = document.getElementById("suggestionList");
        list.innerText = "";

        if (!json.data.length) {
          const li = document.createElement("li");
          const header = document.createElement("h3");
          header.innerText = "No more elements.";
          li.appendChild(header);
          list.appendChild(li);
          isLoading = false;
          loadingInfo.hidden = buttonNext.hidden = true;

          return;
        }

        for (const i of json.data) {
          const li = document.createElement("li");
          const header = document.createElement("h3");

          header.innerText = i.text;
          li.appendChild(header);

          [
            "Author",
            i.author.name,
            "ID",
            i.id,
            "State",
            i.state[0].toUpperCase() + i.state.slice(1).replace(/_/g, " "),
            "Notes"
          ].forEach((value, index) => {
            if (Math.floor(index / 2) === index / 2) {
              const b = document.createElement("b");
              b.innerText = `${value}: `;
              li.appendChild(b);
            } else {
              [document.createTextNode(value), document.createElement("br")].forEach(i => li.appendChild(i));
            }
          });

          const code = document.createElement("code");
          code.innerText = i.notes;

          [document.createElement("br"), code].forEach(i => li.appendChild(i));
          [document.createElement("br"), li].forEach(i => list.appendChild(i));
        }

        if (json.length < json.page_size) {
          buttonNext.hidden = true;
        }

        isLoading = false;
        loadingInfo.hidden = true;
      })
      .catch(() => {
        document.getElementById("loadingFailed").hidden = false;
        document.getElementById("loadingInfo").hidden = true;
      });
  };

  // check the page in the URL.
  const args = String(location).split("?");
  currentPage = 0;
  for (const j of args) {
    const param = j.split("=");
    if (param[0] === "page" && !Number.isNaN(param[1])) {
      currentPage = +param[1];
    }
  }

  load(currentPage);
  setTimeout(() => {
    updatePageNumber();
    if (!currentPage) {
      buttonPrev.hidden = true;
    }

    buttonNext.hidden = false;
    loadingFailed.hidden = true;
  }, 1);

  buttonPrev.onclick = () => {
    if (isLoading) {
      return;
    }

    if (!currentPage) {
      return;
    }

    load(currentPage - 1);
    buttonPrev.hidden = !currentPage;

    scrollTo({ top: 0, behavior: "smooth" });
    loadingInfo.hidden = false;
    buttonNext.hidden = false;
  };
  buttonNext.onclick = () => {
    if (isLoading) {
      return;
    }

    load(currentPage + 1);

    buttonPrev.hidden = !currentPage;

    scrollTo({ top: 0, behavior: "smooth" });
    loadingInfo.hidden = false;
    buttonPrev.hidden = false;
  };;
}());