import QtQuick
import qs
import qs.components

// DESEMPENHO: what the library says about how I play. Numbers, the last eight weeks, most
// played, finished and 100% games, and recommendations: from my own backlog (the genres I
// play most, shortest first) and from outside (IGDB's similar games to the ones I play,
// that I do not have). Nothing invented: no data shows "—".
// Os jogos que já joguei fora da biblioteca (doc.played, da lista em compat-data.json)
// também contam para o gosto e nunca são recomendados. Quem pode não rodar no meu PC
// (Games.warnOf) ganha um aviso [WARN]/[FAIL]; não sai da lista.
Item {
    id: root

    property Item keyTarget: null
    property string title: ""
    readonly property var hints: [["clique", "abre no IGDB"], ["passe o mouse", "joguei / não quero"], [Modules.altKeys, "seção"]]
    // Esta tela não usa teclas próprias.
    function handleKey(event) { return false; }

    readonly property var games: Games.games.filter(g => !g.missing)
    readonly property double nowS: Date.now() / 1000
    // Horas → texto.
    function hours(h) { return Games.hoursLabel(h, "—"); }
    // Timestamp → dd/MM/yy.
    function day(stamp) { return stamp ? Qt.formatDate(new Date(stamp * 1000), "dd/MM/yy") : "—"; }
    // Aviso de "sem versão PC" pelas plataformas do IGDB (null se tem PC ou o IGDB não sabe).
    function noPc(s) { return s.pc === false ? { k: "na", w: "sem versão PC" + (s.platforms && s.platforms.length ? " (" + s.platforms.slice(0, 3).join(", ") + ")" : "") } : null; }
    // Cor do aviso: não roda (vermelho), no limite (amarelo), fora do PC (apagado).
    function warnColor(w) { return w.k === "no" ? Theme.fail : w.k === "lim" ? Theme.warn : Theme.dim; }
    // Etiqueta do aviso depois do nome ("" se roda bem ou não há requisito conhecido).
    function tag(w) { return w ? " <font color='" + warnColor(w) + "'>" + (w.k === "no" ? "[FAIL]" : w.k === "lim" ? "[WARN]" : "[ -- ]") + "</font>" : ""; }
    // Título normalizado para comparar.
    function norm(t) { return String(t || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }

    readonly property var sessions: games.reduce((all, g) => all.concat((g.sessions || []).filter(s => s.end)), [])
    readonly property real monthHours: {
        const now = new Date();
        const since = new Date(now.getFullYear(), now.getMonth(), 1).getTime() / 1000;
        return sessions.filter(s => s.start >= since).reduce((sum, s) => sum + (s.end - s.start) / 3600, 0);
    }
    // Hours per week, oldest first; the last bar is this week (Monday to now).
    readonly property var weeks: {
        const now = new Date();
        const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (now.getDay() + 6) % 7).getTime() / 1000;
        const out = [];
        for (let i = 7; i >= 0; i--) {
            const a = monday - i * 7 * 86400, b = a + 7 * 86400;
            const h = sessions.reduce((sum, s) => sum + Math.max(0, Math.min(s.end, b) - Math.max(s.start, a)) / 3600, 0);
            out.push({ label: Qt.formatDate(new Date(a * 1000), "dd/MM"), hours: h });
        }
        return out;
    }
    readonly property real weekMax: Math.max(1, ...weeks.map(w => w.hours))
    readonly property var mostPlayed: games.filter(g => Games.hoursOf(g) > 0).sort((a, b) => Games.hoursOf(b) - Games.hoursOf(a)).slice(0, 5)
    readonly property real mostMax: mostPlayed.length ? Games.hoursOf(mostPlayed[0]) : 1
    readonly property var finished: games.filter(g => g.status === "done" || g.complete)
                                         .sort((a, b) => (b.complete_at || b.done_at || 0) - (a.complete_at || a.done_at || 0)).slice(0, 6)

    // ---- recommendations --------------------------------------------------------------
    // How much each game says about my taste: hours, finished, 100%, favourite.
    // Raiz quadrada: 300 h pesam ~4x um jogo de 20 h, não 15x; um jogo só não domina as sugestões.
    function soft(w) { return Math.sign(w) * Math.sqrt(Math.abs(w)); }
    function weight(g) { return soft(Games.hoursOf(g) + (g.status === "done" ? 10 : 0) + (g.complete ? 10 : 0) + (g.fav ? 5 : 0) + (g.status === "dropped" ? -5 : 0)); }
    // Já jogados fora da biblioteca: todos zerados; horas e platina pesam como na biblioteca.
    readonly property var played: Object.values(Games.doc.played || {})
    function playedWeight(p) { return soft((p.hrs || 0) + 10 + (p.plat ? 10 : 0)); }
    // "Não quero": ids do IGDB escondidos das sugestões.
    readonly property var hidden: Games.doc.rec_hidden || []
    readonly property var genreWeight: {
        const w = {};
        for (const g of games) if (g.igdb && g.igdb.genres) for (const name of g.igdb.genres) w[name] = (w[name] || 0) + weight(g);
        for (const p of played) if (p.igdb) for (const name of p.igdb.genres) w[name] = (w[name] || 0) + playedWeight(p);
        return w;
    }
    // From the backlog: "quero jogar" games in the genres I play most; shorter first.
    readonly property var fromBacklog: games.filter(g => g.status === "want")
        .map(g => {
            const genres = (g.igdb && g.igdb.genres) || [];
            const best = genres.slice().sort((a, b) => (genreWeight[b] || 0) - (genreWeight[a] || 0))[0] || "";
            return { g: g, score: genres.reduce((sum, n) => sum + Math.max(0, genreWeight[n] || 0), 0), best: best };
        })
        .sort((a, b) => (b.score - a.score) || ((a.g.est_hours || 999) - (b.g.est_hours || 999)))
        .slice(0, 3)
    // From outside: IGDB's similar games of what I play, not in my library.
    readonly property var fromOutside: {
        const similar = Games.doc.igdb_similar || {};
        const mine = new Set(games.map(g => norm(g.title)).concat(games.filter(g => g.igdb && g.igdb.name).map(g => norm(g.igdb.name)))
                             .concat(played.map(p => norm(p.n))).concat(played.filter(p => p.igdb).map(p => norm(p.igdb.name))));
        const ownIds = new Set(games.filter(g => g.igdb && g.igdb.id).map(g => String(g.igdb.id))
                               .concat(played.filter(p => p.igdb).map(p => String(p.igdb.id))));
        const score = {}, because = {}, best = {};
        // Fontes do gosto: a biblioteca e os já jogados, cada uma com seu peso.
        const sources = games.filter(g => g.igdb && g.igdb.similar).map(g => ({ title: g.title, w: weight(g) + 1, similar: g.igdb.similar }))
            .concat(played.filter(p => p.igdb).map(p => ({ title: p.n, w: playedWeight(p), similar: p.igdb.similar })));
        for (const src of sources) {
            if (src.w <= 0) continue;
            for (const id of src.similar) {
                const key = String(id), s = similar[key];
                if (!s || ownIds.has(key) || mine.has(norm(s.name)) || hidden.indexOf(key) >= 0) continue;
                score[key] = (score[key] || 0) + src.w;
                if (!best[key] || best[key] < src.w) { best[key] = src.w; because[key] = src.title; }
            }
        }
        return Object.keys(score)
            .sort((a, b) => (score[b] - score[a]) || ((similar[b].rating || 0) - (similar[a].rating || 0)))
            .slice(0, 5)
            .map(k => Object.assign({ id: k, because: because[k], warn: noPc(similar[k]) || Games.warnOf(similar[k].name) }, similar[k]));
    }

    // ================= HEADER =================
    Item {
        id: header
        width: parent.width
        height: titleText.implicitHeight
        RiceText {
            id: titleText
            textFormat: Text.StyledText
            text: "desempenho<font color='" + Theme.accent + "'>.</font>"
            font.pixelSize: 26
            font.weight: Font.ExtraBold
        }
        RiceText {
            anchors.left: titleText.right
            anchors.leftMargin: 12
            anchors.baseline: titleText.baseline
            text: root.games.length + " jogos · " + root.sessions.length + " sessões"
            color: Theme.dim
        }
    }

    // ================= NUMBERS =================
    Rectangle {
        id: numbers
        anchors.top: header.bottom
        anchors.topMargin: 16
        width: parent.width
        height: 92
        color: Theme.panel
        border.width: 1
        border.color: Theme.line
        Row {
            anchors.centerIn: parent
            Repeater {
                model: [
                    [root.hours(Games.totalHours), "HORAS JOGADAS", Theme.fg],
                    [String(Games.doneCount), "ZERADOS", Theme.ok],
                    [String(root.games.filter(g => g.complete).length), "100%", Theme.yel],
                    [String(root.sessions.length), "SESSÕES", Theme.fg],
                    [root.hours(root.monthHours), "ESTE MÊS", Theme.accent],
                    [root.hours(Games.weeklyPace), "POR SEMANA", Theme.fg]
                ]
                Column {
                    required property var modelData
                    width: numbers.width / 6 - 4
                    spacing: 4
                    RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: modelData[0] === "0" ? "0" : modelData[0]; color: modelData[2]; font.pixelSize: 24; font.weight: Font.ExtraBold }
                    RiceText { anchors.horizontalCenter: parent.horizontalCenter; text: modelData[1]; color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5 }
                }
            }
        }
    }

    component Label: RiceText { color: Theme.faint; font.pixelSize: Theme.small; font.letterSpacing: 1.5; bottomPadding: 6 }
    component Empty: RiceText { color: Theme.faint; font.pixelSize: Theme.small }

    // ================= LEFT: time =================
    Column {
        id: left
        anchors.top: numbers.bottom
        anchors.topMargin: 20
        width: parent.width * 0.5 - 12
        spacing: 18

        Column {
            width: parent.width
            Label { text: "ÚLTIMAS 8 SEMANAS" }
            Row {
                width: parent.width
                height: 96
                spacing: 6
                Repeater {
                    model: root.weeks
                    Item {
                        required property var modelData
                        required property int index
                        width: (parent.width - 7 * 6) / 8
                        height: parent.height
                        Rectangle {
                            anchors.bottom: weekLabel.top
                            anchors.bottomMargin: 4
                            width: parent.width
                            height: Math.max(2, (parent.height - 34) * modelData.hours / root.weekMax)
                            color: index === 7 ? Theme.accent : modelData.hours > 0 ? Qt.alpha(Theme.accent, 0.45) : Theme.line
                        }
                        RiceText {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: weekLabel.top
                            anchors.bottomMargin: Math.max(2, (parent.height - 34) * modelData.hours / root.weekMax) + 6
                            visible: modelData.hours > 0
                            text: root.hours(modelData.hours)
                            color: Theme.dim
                            font.pixelSize: 10
                        }
                        RiceText { id: weekLabel; anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; text: modelData.label; color: Theme.faint; font.pixelSize: 10 }
                    }
                }
            }
        }

        Column {
            width: parent.width
            spacing: 4
            Label { text: "MAIS JOGADOS" }
            Empty { visible: root.mostPlayed.length === 0; text: "— nenhuma hora registrada ainda" }
            Repeater {
                model: root.mostPlayed
                Item {
                    required property var modelData
                    width: parent.width
                    height: 22
                    RiceText { width: parent.width * 0.45; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter; text: modelData.title }
                    Rectangle {
                        x: parent.width * 0.47
                        anchors.verticalCenter: parent.verticalCenter
                        width: (parent.width * 0.53 - 60) * Games.hoursOf(modelData) / root.mostMax
                        height: 6
                        color: Theme.accent
                    }
                    RiceText { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; text: root.hours(Games.hoursOf(modelData)); color: Theme.dim }
                }
            }
        }

        Column {
            width: parent.width
            spacing: 4
            Label { text: "ZERADOS E 100%" }
            Empty { visible: root.finished.length === 0; text: "— nenhum ainda" }
            Repeater {
                model: root.finished
                Item {
                    required property var modelData
                    width: parent.width
                    height: 22
                    RiceText {
                        width: parent.width - 150
                        elide: Text.ElideRight
                        anchors.verticalCenter: parent.verticalCenter
                        textFormat: Text.StyledText
                        text: (modelData.complete ? "<font color='" + Theme.yel + "'>★</font> " : "<font color='" + Theme.ok + "'>✓</font> ") + modelData.title
                    }
                    RiceText {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: (modelData.complete ? "100% " + root.day(modelData.complete_at) : "zerado " + root.day(modelData.done_at))
                        color: Theme.faint
                        font.pixelSize: Theme.small
                    }
                }
            }
        }
    }

    // ================= RIGHT: recommendations =================
    Column {
        anchors.top: numbers.bottom
        anchors.topMargin: 20
        anchors.right: parent.right
        width: parent.width * 0.5 - 12
        spacing: 18

        Column {
            width: parent.width
            spacing: 4
            Label { text: "PRÓXIMO DO BACKLOG" }
            Empty { visible: root.fromBacklog.length === 0; text: "— nada em \"quero jogar\"" }
            Repeater {
                model: root.fromBacklog
                Item {
                    required property var modelData
                    width: parent.width
                    height: 36
                    RiceText {
                        readonly property var warn: Games.warnOf(modelData.g.title)
                        width: parent.width - 70
                        elide: Text.ElideRight
                        textFormat: Text.StyledText
                        text: modelData.g.title + root.tag(warn)
                    }
                    RiceText {
                        y: 17
                        width: parent.width - 70
                        elide: Text.ElideRight
                        text: modelData.best && modelData.score > 0 ? "porque você joga " + modelData.best : (modelData.g.igdb && modelData.g.igdb.genres || []).join(", ") || "sem gênero (IGDB)"
                        color: Theme.faint
                        font.pixelSize: Theme.small
                    }
                    RiceText { anchors.right: parent.right; text: root.hours(modelData.g.est_hours || 0); color: Theme.dim }
                }
            }
        }

        Column {
            width: parent.width
            spacing: 6
            Label { text: "PARECIDOS COM O QUE VOCÊ JOGA" }
            Empty {
                visible: root.fromOutside.length === 0
                width: parent.width
                wrapMode: Text.Wrap
                text: Object.keys(Games.doc.igdb_similar || {}).length ? "— jogue ou zere algo para ter sugestões" : "— sem dados do IGDB ainda (chave em ~/.config/lw/igdb.json)"
            }
            Repeater {
                model: root.fromOutside
                Item {
                    id: rec
                    required property var modelData
                    width: parent.width
                    height: 58
                    Rectangle {
                        id: art
                        width: 40
                        height: 54
                        color: Theme.raise
                        border.width: 1
                        border.color: Theme.line
                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            source: rec.modelData.image ? "https://images.igdb.com/igdb/image/upload/t_cover_small/" + rec.modelData.image + ".jpg" : ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                        }
                    }
                    Column {
                        anchors.left: art.right
                        anchors.leftMargin: 10
                        anchors.right: parent.right
                        anchors.verticalCenter: art.verticalCenter
                        spacing: 1
                        RiceText {
                            width: parent.width
                            elide: Text.ElideRight
                            textFormat: Text.StyledText
                            text: rec.modelData.name + (rec.modelData.year ? " <font color='" + Theme.faint + "'>(" + rec.modelData.year + ")</font>" : "") + root.tag(rec.modelData.warn)
                            color: recMouse.containsMouse ? Theme.accent : Theme.fg
                        }
                        RiceText {
                            width: parent.width
                            elide: Text.ElideRight
                            // Com aviso, o motivo (ex.: "GPU no limite (39 vs 42)") no lugar dos gêneros.
                            text: rec.modelData.warn ? rec.modelData.warn.w
                                : [(rec.modelData.genres || []).slice(0, 2).join(", "), rec.modelData.rating ? "nota " + rec.modelData.rating : ""].filter(x => x).join(" · ") || "—"
                            color: rec.modelData.warn ? root.warnColor(rec.modelData.warn) : Theme.dim
                            font.pixelSize: Theme.small
                        }
                        RiceText { width: parent.width; elide: Text.ElideRight; text: "porque você jogou " + rec.modelData.because; color: Theme.faint; font.pixelSize: Theme.small }
                    }
                    MouseArea {
                        id: recMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: rec.modelData.url ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: if (rec.modelData.url) Qt.openUrlExternally(rec.modelData.url)
                    }
                    // Hover: "já joguei" entra nos já jogados, "não quero" esconde.
                    HoverHandler { id: recHover }
                    Rectangle {
                        visible: recHover.hovered
                        anchors.right: parent.right
                        anchors.verticalCenter: art.verticalCenter
                        width: recButtons.width + 12
                        height: recButtons.height + 8
                        color: Theme.sheet
                        Row {
                            id: recButtons
                            anchors.centerIn: parent
                            spacing: 6
                            AccentButton { ghost: true; label: "✓ joguei"; onClicked: Games.playedAdd(rec.modelData.id, rec.modelData.name) }
                            AccentButton { ghost: true; label: "✕ não quero"; onClicked: Games.recHide(rec.modelData.id, rec.modelData.name) }
                        }
                    }
                }
            }
            RiceText {
                visible: root.hidden.length > 0
                text: root.hidden.length + " escondida(s) · mostrar de novo"
                color: hiddenMouse.containsMouse ? Theme.accent : Theme.faint
                font.pixelSize: Theme.small
                MouseArea { id: hiddenMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Games.recUnhideAll() }
            }
        }
    }
}
