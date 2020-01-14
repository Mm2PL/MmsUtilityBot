/*
 * This is a simple utility bot
 * Copyright (C) 2020 Mm2PL
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

(function suggestion_stats() {
    const loading_failed = document.getElementById("loading_failed");
    const loading_info = document.getElementById("loading_info");
    fetch('https://kotmisia.pl/api/suggestions/stats')
        .then((resp) => resp.json())
        .then((json) => {
            loading_info.hidden = true;
            const suggestion_count = document.getElementById("suggestion_count");
            suggestion_count.appendChild(document.createTextNode(json.count));
            suggestion_count.hidden = false;

            const hidden_suggestion_count = document.getElementById("hidden_suggestion_count");
            hidden_suggestion_count.appendChild(document.createTextNode(json.count_hidden));
            hidden_suggestion_count.hidden = false;

            const state_stats = document.getElementById("state_stats");
            for (const [key, value] of Object.entries(json.states)) {
                let li = document.createElement("li");

                let name = document.createElement("strong");
                name.innerText = key + ": ";
                li.appendChild(name);

                let val = document.createTextNode(value);
                li.appendChild(val);

                state_stats.appendChild(li);
            }

            const top_suggesters = document.getElementById("top_suggesters");
            for (let i = 0; i < json.top_users.length; i++) {
                const user = json.top_users[i];

                let li = document.createElement("li");

                let name = document.createElement("strong");
                name.innerText = `${user.name} - ${user.count}`;
                li.appendChild(name);
                top_suggesters.appendChild(li);
            }
        })
        .catch(() => {
            loading_failed.hidden = false;
            loading_info.hidden = true;
        });
}());
