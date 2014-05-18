var riverApp = angular.module('riverApp', ['ngSanitize']);

riverApp.filter('convertDate', function() {
    return function(input) {
	return Date.parse(input);
    };
});

riverApp.controller('RiverController', ['$scope', '$http', function($scope, $http) {
    $scope.$watch('currentRiver', function() {
	if ($scope.currentRiver) {
	    $http.get($scope.currentRiver.url).success(function(obj) {
		$scope.riverObj = obj;
	    });
	}
    });

    $http.get('manifest.js').success(function(obj) {
	$scope.rivers = obj;
	$scope.currentRiver = obj[0];
    });
}]);
