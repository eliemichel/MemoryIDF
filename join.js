// **************************************************
// Author : Élie Michel <elie.michel@exppad.com>
// MIT License - Copyright (c) 2017 Élie Michel.
// See https://github.com/eliemichel/join.js
// **************************************************
"use strict";

function join() {
    // MIT licensed, copyright (c) 2017 -- Elie Michel <elie.michel@exppad.com>
    let promises = Array.prototype.slice.call(arguments, 0, arguments.length - 1);
    let spreadResolve = arguments[arguments.length - 1];
    let resolve = function(args) { return spreadResolve.apply(this, args); }

    return Promise.all(promises)
    .then(resolve)
    .catch(console.error.bind(console));
}

function decoratedJoin(decorator) {
    // MIT licensed, copyright (c) 2017 -- Elie Michel <elie.michel@exppad.com>
    return function() {
        let args = Array.prototype.map.call(arguments, function(value, i) {
            return i < arguments.length - 1 ? decorator(value) : value;
        });
        return join.apply(this, args);
    }
}

