document.addEventListener("DOMContentLoaded", () => {

  // =========================================
  // DOM
  // =========================================

  const backendStatus =
      document.getElementById("backend-status");

  const agentPanel =
      document.querySelector(".agent-panel");

  const agentForm =
      document.getElementById("agent-form");

  const agentInput =
      document.getElementById("agent-input");

  const agentSubmit =
      document.getElementById("agent-submit");

  const agentState =
      document.getElementById("agent-state");

  const agentProgress =
      document.getElementById("agent-progress");

  const progressFill =
      document.getElementById("progress-fill");

  const progressObserve =
      document.getElementById("progress-observe");

  const progressPlan =
      document.getElementById("progress-plan");

  const progressAct =
      document.getElementById("progress-act");

  const progressComplete =
      document.getElementById("progress-complete");

  const agentResult =
      document.getElementById("agent-result");

  const agentAnswer =
      document.getElementById("agent-answer");

  const resultSteps =
      document.getElementById("result-steps");

  const resultActions =
      document.getElementById("result-actions");

  const agentError =
      document.getElementById("agent-error");

  const agentErrorMessage =
      document.getElementById(
          "agent-error-message"
      );

  const memberIdInput =
      document.getElementById("member-id");

  const searchButton =
      document.getElementById("search-button");

  const lookupMessage =
      document.getElementById("lookup-message");

  const memberResults =
      document.getElementById("member-results");

  const contextTitle =
      document.getElementById("context-title");

  const contextStatus =
      document.getElementById("context-status");

  const contextCopy =
      document.getElementById("context-copy");

  const memberName =
      document.getElementById("member-name");

  const memberNumber =
      document.getElementById("member-number");

  const memberEmail =
      document.getElementById("member-email");

  const memberPhone =
      document.getElementById("member-phone");

  const memberDob =
      document.getElementById("member-dob");

  const memberInitials =
      document.getElementById("member-initials");

  const memberActiveStatus =
      document.getElementById(
          "member-active-status"
      );

  const accountCount =
      document.getElementById("account-count");

  const transactionCount =
      document.getElementById(
          "transaction-count"
      );

  const claimCount =
      document.getElementById("claim-count");

  const accountsContainer =
      document.getElementById(
          "accounts-container"
      );

  const transactionsContainer =
      document.getElementById(
          "transactions-container"
      );

  const claimsContainer =
      document.getElementById(
          "claims-container"
      );


  // =========================================
  // STATE
  // =========================================

  let currentMember = null;
  let transactionFilter = "all";
  let claimFilter = "all";
  let agentRunning = false;


  // =========================================
  // HELPERS
  // =========================================

  function escapeHtml(value) {

      return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
  }


  function firstValue(object, keys, fallback = "—") {

      for (const key of keys) {

          const value = object?.[key];

          if (
              value !== undefined &&
              value !== null &&
              value !== ""
          ) {
              return value;
          }
      }

      return fallback;
  }


  function formatMoney(value) {

      const number = Number(value);

      if (!Number.isFinite(number)) {
          return String(value ?? "—");
      }

      return new Intl.NumberFormat(
          "en-US",
          {
              style: "currency",
              currency: "USD",
          }
      ).format(number);
  }


  function normalize(value) {

      return String(value ?? "")
          .trim()
          .toLowerCase();
  }


  function getMemberId(member) {

      return firstValue(
          member,
          [
              "member_id",
              "memberId",
              "id",
              "member_number",
          ],
          ""
      );
  }


  function getMemberName(member) {

      const directName = firstValue(
          member,
          [
              "name",
              "full_name",
              "fullName",
          ],
          ""
      );

      if (directName) {
          return directName;
      }

      const firstName = firstValue(
          member,
          [
              "first_name",
              "firstName",
          ],
          ""
      );

      const lastName = firstValue(
          member,
          [
              "last_name",
              "lastName",
          ],
          ""
      );

      return `${firstName} ${lastName}`.trim()
          || "Member";
  }


  function getInitials(name) {

      return String(name)
          .split(/\s+/)
          .filter(Boolean)
          .slice(0, 2)
          .map(part => part[0])
          .join("")
          .toUpperCase()
          || "M";
  }


  function getAccounts(member) {

      return Array.isArray(member?.accounts)
          ? member.accounts
          : [];
  }


  function getTransactions(member) {

      return Array.isArray(member?.transactions)
          ? member.transactions
          : [];
  }


  function getClaims(member) {

      return Array.isArray(member?.claims)
          ? member.claims
          : [];
  }


  function scrollToSection(id) {

      document
          .getElementById(id)
          ?.scrollIntoView({
              behavior: "smooth",
              block: "start",
          });
  }


  // =========================================
  // BACKEND HEALTH
  // =========================================

  async function checkBackend() {

      try {

          const response =
              await fetch("/api/health");

          if (!response.ok) {
              throw new Error();
          }

          backendStatus.classList.remove(
              "offline"
          );

          backendStatus.innerHTML = `
              <span class="status-dot"></span>
              Connected
          `;

      } catch {

          backendStatus.classList.add(
              "offline"
          );

          backendStatus.innerHTML = `
              <span class="status-dot"></span>
              Offline
          `;
      }
  }


  checkBackend();


  // =========================================
  // MEMBER SEARCH
  // =========================================

  async function searchMember(id, options = {}) {

      const memberId =
          String(id ?? "").trim();

      if (!memberId) {

          showLookupError(
              "Enter a member ID."
          );

          return null;
      }

      if (!/^\d+$/.test(memberId)) {

          showLookupError(
              "Member ID must be numeric."
          );

          return null;
      }

      lookupMessage.classList.remove(
          "error"
      );

      lookupMessage.textContent =
          "Searching member records...";

      searchButton.disabled = true;

      try {

          const response = await fetch(
              `/api/member/${encodeURIComponent(
                  memberId
              )}`
          );

          const data =
              await response.json();

          if (!response.ok) {

              throw new Error(
                  data.error
                  || "Member not found."
              );
          }

          currentMember = data;

          renderMember(data);

          lookupMessage.textContent =
              "Member loaded.";

          if (!options.silentScroll) {

              memberResults.scrollIntoView({
                  behavior: "smooth",
                  block: "start",
              });
          }

          return data;

      } catch (error) {

          showLookupError(
              error.message
              || "Unable to load member."
          );

          return null;

      } finally {

          searchButton.disabled = false;
      }
  }


  function showLookupError(message) {

      lookupMessage.classList.add(
          "error"
      );

      lookupMessage.textContent =
          message;
  }


  searchButton.addEventListener(
      "click",
      () => {
          searchMember(
              memberIdInput.value
          );
      }
  );


  memberIdInput.addEventListener(
      "keydown",
      event => {

          if (event.key === "Enter") {

              event.preventDefault();

              searchMember(
                  memberIdInput.value
              );
          }
      }
  );


  // =========================================
  // MEMBER RENDER
  // =========================================

  function renderMember(member) {

      const name =
          getMemberName(member);

      const id =
          getMemberId(member);

      const status =
          firstValue(
              member,
              [
                  "status",
                  "member_status",
              ],
              "Unknown"
          );

      const accounts =
          getAccounts(member);

      const transactions =
          getTransactions(member);

      const claims =
          getClaims(member);

      memberName.textContent =
          name;

      memberNumber.textContent =
          id || "—";

      memberEmail.textContent =
          firstValue(
              member,
              ["email"],
              "—"
          );

      memberPhone.textContent =
          firstValue(
              member,
              [
                  "phone",
                  "phone_number",
              ],
              "—"
          );

      memberDob.textContent =
          firstValue(
              member,
              [
                  "dob",
                  "date_of_birth",
                  "dateOfBirth",
              ],
              "—"
          );

      memberInitials.textContent =
          getInitials(name);

      memberActiveStatus.textContent =
          status;

      const isActive =
          normalize(status) === "active";

      memberActiveStatus.classList.toggle(
          "inactive",
          !isActive
      );

      accountCount.textContent =
          accounts.length;

      transactionCount.textContent =
          transactions.length;

      claimCount.textContent =
          claims.length;

      contextTitle.textContent =
          name;

      contextStatus.textContent =
          status;

      contextStatus.classList.toggle(
          "active",
          isActive
      );

      contextCopy.textContent =
          `Member ${id}. `
          + `${accounts.length} accounts, `
          + `${transactions.length} transactions, `
          + `${claims.length} claims.`;

      transactionFilter = "all";
      claimFilter = "all";

      resetFilterButtons();

      renderAccounts(accounts);
      renderTransactions(transactions);
      renderClaims(claims);

      memberResults.classList.remove(
          "hidden"
      );
  }


  // =========================================
  // ACCOUNTS
  // =========================================

  function renderAccounts(accounts) {

      if (!accounts.length) {

          accountsContainer.innerHTML = `
              <div class="empty-state">
                  No accounts found.
              </div>
          `;

          return;
      }

      accountsContainer.innerHTML =
          accounts.map(account => {

              const accountNumber =
                  firstValue(
                      account,
                      [
                          "account_number",
                          "account_id",
                          "accountId",
                          "id",
                      ]
                  );

              const accountType =
                  firstValue(
                      account,
                      [
                          "account_type",
                          "type",
                          "name",
                      ],
                      "Account"
                  );

              const status =
                  firstValue(
                      account,
                      ["status"],
                      "Active"
                  );

              const balance =
                  firstValue(
                      account,
                      [
                          "balance",
                          "current_balance",
                          "amount",
                      ],
                      null
                  );

              return `
                  <article class="account-card">

                      <div class="account-card-top">

                          <h4>
                              ${escapeHtml(
                                  accountType
                              )}
                          </h4>

                          <span class="account-status">
                              ${escapeHtml(
                                  status
                              )}
                          </span>

                      </div>

                      <div class="account-number">
                          ${escapeHtml(
                              accountNumber
                          )}
                      </div>

                      ${
                          balance !== null
                          ? `
                              <div class="account-balance">
                                  ${escapeHtml(
                                      formatMoney(
                                          balance
                                      )
                                  )}
                              </div>
                          `
                          : ""
                      }

                  </article>
              `;
          }).join("");
  }


  // =========================================
  // TRANSACTIONS
  // =========================================

  function transactionAmount(transaction) {

      return Number(
          firstValue(
              transaction,
              [
                  "amount",
                  "transaction_amount",
              ],
              0
          )
      ) || 0;
  }


  function renderTransactions(
      transactions
  ) {

      let filtered =
          [...transactions];

      if (
          transactionFilter
          === "largest"
      ) {

          filtered.sort(
              (a, b) =>
                  transactionAmount(b)
                  -
                  transactionAmount(a)
          );

          filtered =
              filtered.slice(0, 1);
      }

      if (
          transactionFilter
          === "credit"
      ) {

          filtered =
              filtered.filter(
                  transaction =>
                      normalize(
                          firstValue(
                              transaction,
                              [
                                  "type",
                                  "transaction_type",
                              ],
                              ""
                          )
                      ) === "credit"
              );
      }

      if (
          transactionFilter
          === "debit"
      ) {

          filtered =
              filtered.filter(
                  transaction =>
                      normalize(
                          firstValue(
                              transaction,
                              [
                                  "type",
                                  "transaction_type",
                              ],
                              ""
                          )
                      ) === "debit"
              );
      }


      if (!filtered.length) {

          transactionsContainer.innerHTML = `
              <div class="empty-state">
                  No transactions found.
              </div>
          `;

          return;
      }


      transactionsContainer.innerHTML =
          filtered.map(transaction => {

              const date =
                  firstValue(
                      transaction,
                      [
                          "date",
                          "transaction_date",
                          "created_at",
                      ]
                  );

              const account =
                  firstValue(
                      transaction,
                      [
                          "account",
                          "account_number",
                          "account_id",
                      ]
                  );

              const merchant =
                  firstValue(
                      transaction,
                      [
                          "merchant",
                          "merchant_name",
                          "description",
                      ]
                  );

              const type =
                  firstValue(
                      transaction,
                      [
                          "type",
                          "transaction_type",
                      ],
                      "—"
                  );

              const amount =
                  transactionAmount(
                      transaction
                  );

              return `
                  <div
                      class="transaction-row"
                      data-amount="${amount}"
                      data-type="${escapeHtml(
                          normalize(type)
                      )}"
                  >

                      <span>
                          ${escapeHtml(date)}
                      </span>

                      <span>
                          ${escapeHtml(account)}
                      </span>

                      <span>
                          ${escapeHtml(merchant)}
                      </span>

                      <span>
                          <span
                              class="
                                  transaction-type
                                  ${escapeHtml(
                                      normalize(type)
                                  )}
                              "
                          >
                              ${escapeHtml(type)}
                          </span>
                      </span>

                      <span class="amount">
                          ${escapeHtml(
                              formatMoney(amount)
                          )}
                      </span>

                  </div>
              `;
          }).join("");
  }


  document
      .querySelectorAll(
          "[data-transaction-filter]"
      )
      .forEach(button => {

          button.addEventListener(
              "click",
              () => {

                  transactionFilter =
                      button.dataset
                          .transactionFilter;

                  document
                      .querySelectorAll(
                          "[data-transaction-filter]"
                      )
                      .forEach(item =>
                          item.classList.remove(
                              "active"
                          )
                      );

                  button.classList.add(
                      "active"
                  );

                  if (currentMember) {

                      renderTransactions(
                          getTransactions(
                              currentMember
                          )
                      );
                  }
              }
          );
      });


  // =========================================
  // CLAIMS
  // =========================================

  function renderClaims(claims) {

      let filtered =
          [...claims];

      if (
          claimFilter === "pending"
      ) {

          filtered =
              filtered.filter(
                  claim =>
                      normalize(
                          firstValue(
                              claim,
                              ["status"],
                              ""
                          )
                      ) === "pending"
              );
      }


      if (!filtered.length) {

          claimsContainer.innerHTML = `
              <div class="empty-state">
                  No claims found.
              </div>
          `;

          return;
      }


      claimsContainer.innerHTML =
          filtered.map(claim => {

              const claimId =
                  firstValue(
                      claim,
                      [
                          "claim_id",
                          "claim_number",
                          "id",
                      ]
                  );

              const status =
                  firstValue(
                      claim,
                      ["status"],
                      "Unknown"
                  );

              const amount =
                  firstValue(
                      claim,
                      [
                          "amount",
                          "claim_amount",
                      ],
                      null
                  );

              const date =
                  firstValue(
                      claim,
                      [
                          "date",
                          "claim_date",
                          "submitted_date",
                      ]
                  );

              const provider =
                  firstValue(
                      claim,
                      [
                          "provider",
                          "provider_name",
                          "description",
                      ]
                  );

              return `
                  <article class="claim-card">

                      <div class="claim-top">

                          <span class="claim-id">
                              ${escapeHtml(
                                  claimId
                              )}
                          </span>

                          <span
                              class="
                                  claim-status
                                  ${escapeHtml(
                                      normalize(
                                          status
                                      )
                                  )}
                              "
                          >
                              ${escapeHtml(
                                  status
                              )}
                          </span>

                      </div>

                      <div class="claim-details">

                          <div>
                              <span>Date</span>

                              <strong>
                                  ${escapeHtml(
                                      date
                                  )}
                              </strong>
                          </div>

                          <div>
                              <span>Provider</span>

                              <strong>
                                  ${escapeHtml(
                                      provider
                                  )}
                              </strong>
                          </div>

                          ${
                              amount !== null
                              ? `
                                  <div>
                                      <span>
                                          Amount
                                      </span>

                                      <strong>
                                          ${escapeHtml(
                                              formatMoney(
                                                  amount
                                              )
                                          )}
                                      </strong>
                                  </div>
                              `
                              : ""
                          }

                      </div>

                  </article>
              `;
          }).join("");
  }


  document
      .querySelectorAll(
          "[data-claim-filter]"
      )
      .forEach(button => {

          button.addEventListener(
              "click",
              () => {

                  claimFilter =
                      button.dataset
                          .claimFilter;

                  document
                      .querySelectorAll(
                          "[data-claim-filter]"
                      )
                      .forEach(item =>
                          item.classList.remove(
                              "active"
                          )
                      );

                  button.classList.add(
                      "active"
                  );

                  if (currentMember) {

                      renderClaims(
                          getClaims(
                              currentMember
                          )
                      );
                  }
              }
          );
      });


  function resetFilterButtons() {

      document
          .querySelectorAll(
              "[data-transaction-filter]"
          )
          .forEach(button => {

              button.classList.toggle(
                  "active",
                  button.dataset
                      .transactionFilter
                      === "all"
              );
          });

      document
          .querySelectorAll(
              "[data-claim-filter]"
          )
          .forEach(button => {

              button.classList.toggle(
                  "active",
                  button.dataset
                      .claimFilter
                      === "all"
              );
          });
  }


  // =========================================
  // LIVE PYTHON AGENT
  // =========================================

  async function runAgent(task) {

      task =
          String(task ?? "").trim();

      if (!task || agentRunning) {
          return;
      }

      agentRunning = true;

      clearAgentHighlights();

      agentResult.classList.add(
          "hidden"
      );

      agentError.classList.add(
          "hidden"
      );

      agentProgress.classList.remove(
          "hidden"
      );

      agentPanel.classList.add(
          "running"
      );

      agentSubmit.disabled = true;

      setAgentState(
          "Observing portal..."
      );

      resetProgress();

      activateProgress(
          progressObserve,
          20
      );


      /*
       * The backend call remains open while
       * the real Python browser agent performs
       * the task.
       *
       * The progress states below are UI
       * feedback only. The final answer itself
       * comes exclusively from /api/agent.
       */

      const planTimer =
          setTimeout(() => {

              setAgentState(
                  "Planning next action..."
              );

              activateProgress(
                  progressPlan,
                  45
              );

          }, 900);


      const actTimer =
          setTimeout(() => {

              setAgentState(
                  "Operating workspace..."
              );

              activateProgress(
                  progressAct,
                  72
              );

          }, 2100);


      try {

          const response =
              await fetch(
                  "/api/agent",
                  {
                      method: "POST",

                      headers: {
                          "Content-Type":
                              "application/json",
                      },

                      body: JSON.stringify({
                          task,
                      }),
                  }
              );


          const data =
              await response.json();


          clearTimeout(planTimer);
          clearTimeout(actTimer);


          if (
              !response.ok
              ||
              !data.success
          ) {

              throw new Error(
                  data.error
                  ||
                  "Agent could not complete "
                  + "the task."
              );
          }


          activateProgress(
              progressObserve,
              100
          );

          activateProgress(
              progressPlan,
              100
          );

          activateProgress(
              progressAct,
              100
          );

          activateProgress(
              progressComplete,
              100
          );


          setAgentState(
              "Complete"
          );


          agentAnswer.textContent =
              data.answer
              || "Task completed.";


          resultSteps.textContent =
              data.steps ?? "—";


          resultActions.textContent =
              data.action_count
              ?? data.actions?.length
              ?? "—";


          agentResult.classList.remove(
              "hidden"
          );


          enhanceWorkspaceFromTask(
              task,
              data.answer
          );


      } catch (error) {

          clearTimeout(planTimer);
          clearTimeout(actTimer);

          setAgentState(
              "Stopped"
          );

          agentErrorMessage.textContent =
              error.message
              || "Something went wrong.";

          agentError.classList.remove(
              "hidden"
          );


      } finally {

          agentRunning = false;

          agentSubmit.disabled = false;

          agentPanel.classList.remove(
              "running"
          );
      }
  }


  agentForm.addEventListener(
      "submit",
      event => {

          event.preventDefault();

          const task =
              agentInput.value.trim();

          if (!task) {
              agentInput.focus();
              return;
          }

          runAgent(task);
      }
  );


  agentInput.addEventListener(
      "keydown",
      event => {

          if (
              event.key === "Enter"
              &&
              !event.shiftKey
          ) {

              event.preventDefault();

              agentForm.requestSubmit();
          }
      }
  );


  agentInput.addEventListener(
      "input",
      () => {

          agentInput.style.height =
              "auto";

          agentInput.style.height =
              Math.min(
                  agentInput.scrollHeight,
                  130
              )
              + "px";
      }
  );


  document
      .querySelectorAll(
          ".suggestion"
      )
      .forEach(button => {

          button.addEventListener(
              "click",
              () => {

                  const task =
                      button.dataset.task;

                  agentInput.value =
                      task;

                  runAgent(task);
              }
          );
      });


  // =========================================
  // AGENT VISUAL STATE
  // =========================================

  function setAgentState(text) {

      agentState.innerHTML = `
          <span></span>
          ${escapeHtml(text)}
      `;
  }


  function resetProgress() {

      progressFill.style.width =
          "0%";

      [
          progressObserve,
          progressPlan,
          progressAct,
          progressComplete,
      ].forEach(step => {

          step.classList.remove(
              "active"
          );
      });
  }


  function activateProgress(
      element,
      percentage
  ) {

      element.classList.add(
          "active"
      );

      progressFill.style.width =
          `${percentage}%`;
  }


  // =========================================
  // VISUALIZE AGENT RESULT
  // =========================================

  function clearAgentHighlights() {

      document
          .querySelectorAll(
              ".transaction-row"
          )
          .forEach(row => {

              row.classList.remove(
                  "agent-highlight",
                  "agent-dim"
              );
          });
  }


  function enhanceWorkspaceFromTask(
      task,
      answer
  ) {

      const lowerTask =
          normalize(task);

      const memberIdMatch =
          task.match(/\b10\d{3}\b/);

      /*
       * The Python agent may have searched
       * member 10002 inside its own browser.
       *
       * Load the same member into the operator's
       * visible workspace so the answer and
       * evidence are shown together.
       */

      if (memberIdMatch) {

          const id =
              memberIdMatch[0];

          memberIdInput.value =
              id;

          searchMember(
              id,
              {
                  silentScroll: true,
              }
          ).then(() => {

              applyTaskHighlight(
                  lowerTask,
                  answer
              );
          });

          return;
      }


      applyTaskHighlight(
          lowerTask,
          answer
      );
  }


  function applyTaskHighlight(
      task,
      answer
  ) {

      if (!currentMember) {
          return;
      }


      // Largest transaction

      if (
          task.includes("largest")
          ||
          task.includes("biggest")
          ||
          task.includes("highest")
      ) {

          transactionFilter =
              "all";

          renderTransactions(
              getTransactions(
                  currentMember
              )
          );

          const rows =
              [
                  ...document.querySelectorAll(
                      ".transaction-row"
                  )
              ];

          if (rows.length) {

              const largest =
                  rows.reduce(
                      (winner, row) => {

                          return (
                              Number(
                                  row.dataset.amount
                              )
                              >
                              Number(
                                  winner.dataset.amount
                              )
                          )
                              ? row
                              : winner;
                      }
                  );

              rows.forEach(row => {

                  row.classList.toggle(
                      "agent-highlight",
                      row === largest
                  );

                  row.classList.toggle(
                      "agent-dim",
                      row !== largest
                  );
              });

              scrollToSection(
                  "transactions-section"
              );
          }

          return;
      }


      // Pending claims

      if (
          task.includes("pending")
          &&
          task.includes("claim")
      ) {

          claimFilter =
              "pending";

          renderClaims(
              getClaims(
                  currentMember
              )
          );

          document
              .querySelectorAll(
                  "[data-claim-filter]"
              )
              .forEach(button => {

                  button.classList.toggle(
                      "active",
                      button.dataset
                          .claimFilter
                          === "pending"
                  );
              });

          scrollToSection(
              "claims-section"
          );

          return;
      }


      // Transactions over a threshold

      const thresholdMatch =
          task.match(
              /(?:over|above|greater than)\s*\$?([\d,]+(?:\.\d+)?)/i
          );


      if (
          thresholdMatch
          &&
          task.includes(
              "transaction"
          )
      ) {

          const threshold =
              Number(
                  thresholdMatch[1]
                      .replaceAll(",", "")
              );


          transactionFilter =
              "all";


          renderTransactions(
              getTransactions(
                  currentMember
              )
          );


          document
              .querySelectorAll(
                  ".transaction-row"
              )
              .forEach(row => {

                  const amount =
                      Number(
                          row.dataset.amount
                      );

                  if (
                      amount > threshold
                  ) {

                      row.classList.add(
                          "agent-highlight"
                      );

                  } else {

                      row.classList.add(
                          "agent-dim"
                      );
                  }
              });


          scrollToSection(
              "transactions-section"
          );

          return;
      }


      // Claims

      if (
          task.includes("claim")
      ) {

          scrollToSection(
              "claims-section"
          );

          return;
      }


      // Accounts

      if (
          task.includes("account")
      ) {

          scrollToSection(
              "accounts-section"
          );
      }
  }


  // =========================================
  // STAT CARDS
  // =========================================

  document
      .querySelectorAll(
          ".stat-card"
      )
      .forEach(card => {

          card.addEventListener(
              "click",
              () => {

                  scrollToSection(
                      card.dataset.target
                  );
              }
          );
      });


  // =========================================
  // SIDEBAR
  // =========================================

  document
      .getElementById(
          "nav-members"
      )
      .addEventListener(
          "click",
          () => {

              scrollToSection(
                  "member-workspace"
              );

              memberIdInput.focus();
          }
      );


  document
      .getElementById(
          "nav-transactions"
      )
      .addEventListener(
          "click",
          () => {

              if (currentMember) {

                  scrollToSection(
                      "transactions-section"
                  );
              }
          }
      );


  document
      .getElementById(
          "nav-claims"
      )
      .addEventListener(
          "click",
          () => {

              if (currentMember) {

                  scrollToSection(
                      "claims-section"
                  );
              }
          }
      );


  // =========================================
  // KEYBOARD SHORTCUT
  // =========================================

  document.addEventListener(
      "keydown",
      event => {

          if (
              event.key === "/"
              &&
              document.activeElement
                  !== agentInput
              &&
              document.activeElement
                  !== memberIdInput
          ) {

              event.preventDefault();

              agentInput.focus();
          }
      }
  );

});